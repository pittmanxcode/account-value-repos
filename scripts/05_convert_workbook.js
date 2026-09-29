// Convert tmp/<slug>_value_repository.xlsx.json into outputs/<Company> × Factory Value.xlsx
// Run from anywhere: node scripts/05_convert_workbook.js [slug]
// Requires exceljs installed under tmp/ (npm install --prefix tmp exceljs).
//
// NAMING STANDARD for all account workbooks:
//   outputs/{Company} × Factory Value.xlsx
// where {Company} is the display name with an initial capital
// (e.g. "Crunchyroll × Factory Value.xlsx"). Keep the " × " separator.
const path = require("path");
const fs = require("fs");
module.paths.push(path.join(__dirname, "..", "tmp", "node_modules"));
const ExcelJS = require("exceljs");

const slug = process.argv[2] || "crunchyroll";
const display = slug.charAt(0).toUpperCase() + slug.slice(1);
const specPath = path.join(__dirname, "..", "tmp", `${slug}_value_repository.xlsx.json`);
const outPath = path.join(__dirname, "..", "outputs", `${display} × Factory Value.xlsx`);
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));

(async () => {
  const wb = new ExcelJS.Workbook();
  wb.creator = "Factory Droid";
  for (const s of spec.sheets) {
    const ws = wb.addWorksheet(s.name, {
      views: s.freezeRows ? [{ state: "frozen", ySplit: s.freezeRows }] : undefined,
    });
    if (s.columns) ws.columns = s.columns.map((c) => ({ width: c.width || 12 }));
    for (const row of s.rows) {
      const r = ws.addRow(
        row.map((cell) => {
          if (cell === null || cell === undefined) return "";
          if (typeof cell === "object") return cell.value ?? "";
          return cell;
        })
      );
      row.forEach((cell, i) => {
        const c = r.getCell(i + 1);
        if (cell && typeof cell === "object") {
          if (cell.numFmt) c.numFmt = cell.numFmt;
          if (cell.bold) c.font = { bold: true, color: cell.color ? { argb: cell.color } : undefined };
          if (cell.fill) c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: cell.fill } };
          if (cell.color && !cell.bold) c.font = { color: { argb: cell.color } };
          if (cell.align === "right") c.alignment = { horizontal: "right" };
        }
      });
    }
  }
  await wb.xlsx.writeFile(outPath);
  console.log(`written: ${outPath} (${(fs.statSync(outPath).size / 1024).toFixed(1)} KB)`);
})();
