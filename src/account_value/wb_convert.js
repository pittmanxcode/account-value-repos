// Convert a validated workbook spec JSON into a real .xlsx (ExcelJS).
// Usage: node wb_convert.js <spec.json> <out.xlsx>
// ExcelJS resolves from tmp/node_modules relative to the project root.
const path = require("path");
const fs = require("fs");
module.paths.push(path.join(process.cwd(), "tmp", "node_modules"));
const ExcelJS = require("exceljs");

const [specPath, outPath] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));

(async () => {
  const wb = new ExcelJS.Workbook();
  wb.creator = "account-value (Factory Droid)";
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
