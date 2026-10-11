"""Posted pay in every format seen across the 28 boards on 2026-10-10."""
import pytest

from account_value.parse import extract_posted_pay, extract_posted_pay_detail, fx_rates


def _detail(text: str):
    return extract_posted_pay_detail(f"<p>{text}</p>")


def test_greenhouse_html_block_still_wins():
    html = ('<div class="pay-range"><span>$140,000</span></div> - '
            '<div class="pay-range"><span>$180,000</span></div>'
            "<p>Base Salary Range: $1 and $2</p>")
    pay = extract_posted_pay_detail(html)
    assert (pay.min_usd, pay.max_usd, pay.mid_usd, pay.note) == (140000, 180000, 160000, "html block")


@pytest.mark.parametrize("line, expected", [
    # Greenhouse text (Blend): "and" as the separator
    ("Base Salary Range: $125,000 and $150,000 (OTE includes base + variable)", (125000, 150000)),
    # Greenhouse text with an en dash
    ("Base Salary Range: $163,000 – $191,000 (This applies to full time hires.)", (163000, 191000)),
    # Lever (Achievers)
    ("$106,000 - $125,000 reflects what we reasonably expect to offer for this role based on "
     "current market data. The final offer will depend on several factors.", (106000, 125000)),
    # Ashby (Valon): K suffix on one side only, and on both
    ("Base Compensation Band: $180K - 230K. Base salary offered is determined by factors.", (180000, 230000)),
    ("Compensation: competitive salary range of $135K–$240K with a meaningful stake", (135000, 240000)),
    # Ashby (Valon): "to"
    ("Base salary band : $148,750 to $201,250", (148750, 201250)),
    # Oscar (Greenhouse text): "The base pay for this role is"
    ("The base pay for this role is: $218,592.00 - $286,902.00 per year.", (218592, 286902)),
    # Oscar: no space before the dash
    ("Pay Transparency: The base pay for this role is: $135,000- $176,000 per year.", (135000, 176000)),
    # DigitalOcean: stray period after the first amount
    ("$131,200. - $164,000", (131200, 164000)),
    # Valon: "401k plan" on the same line must not exclude it
    ("Compensation: competitive salary range of $175K–$225K with a meaningful stake in the company "
     "via equity, and 401k plan.", (175000, 225000)),
    # Filevine (Lever additional block): second figure without a symbol
    ("Compensation Information: $130,000 - 170,000", (130000, 170000)),
    # Reddit / Fivetran: bare range with trailing code, no pay word on the line
    ("$245,800 — $344,100 USD", (245800, 344100)),
    # Turo (Workday): a space before the thousands comma
    ("For this role, the target base salary range in San Francisco is $175 ,000 - $220,000 annually.",
     (175000, 220000)),
    # DigitalOcean: bare, one symbol, no spaces
    ("$167,200-209,000", (167200, 209000)),
])


def test_usd_text_ranges(line, expected):
    pay = _detail(line)
    assert (pay.min_usd, pay.max_usd) == expected
    assert pay.mid_usd == round(sum(expected) / 2)
    assert pay.note == "text"


def test_entity_escaped_greenhouse_content_is_unescaped_first():
    escaped = ("&lt;div&gt;&lt;p&gt;About the role&lt;/p&gt;&lt;p&gt;" + "x " * 900 +
               "&lt;/p&gt;&lt;p&gt;San Francisco and New York : The pay range for this role is "
               "$ 116,000 to $ 159,500 per year.&lt;/p&gt;&lt;/div&gt;")
    pay = extract_posted_pay_detail(escaped)
    assert (pay.min_usd, pay.max_usd, pay.note) == (116000, 159500, "text")

def test_per_year_up_to_range_is_read_as_a_range():
    # Coalition (Greenhouse text, Canadian provinces): "$X/year up to $Y/year"
    pay = _detail("In Alberta, British Columbia & Ontario the base salary for this position ranges "
                  "from $160,600.00/year up to $210,600.00/year.")
    assert (pay.min_usd, pay.max_usd) == (160600, 210600)
    assert pay.note == "text"


def test_pay_inside_a_long_paragraph_is_still_found():
    filler = "You are also eligible for employee benefits including generous PTO, sick leave, " * 12
    pay = _detail(f"Pay Transparency: The base pay for this role is: $135,000- $176,000 per year. {filler}")
    assert (pay.min_usd, pay.max_usd) == (135000, 176000)


def test_workday_cad_and_gbp_are_converted_and_labelled():
    rates, label = fx_rates()
    cad = _detail("The expected salary range for this role is $116,100 to $157,100 CAD. "
                  "Initial placement within the range is informed by geographic region.")
    assert cad.min_usd == round(116100 * rates["CAD"]) and cad.max_usd == round(157100 * rates["CAD"])
    assert cad.note.startswith("text, CAD at") and label in cad.note
    gbp = _detail("The expected salary range for this role is £64,900 to £87,900 GBP.")
    assert gbp.min_usd == round(64900 * rates["GBP"])
    assert "GBP at" in gbp.note


def test_monthly_eur_is_annualized():
    pay = _detail("Compensation : €4,116 – €6,183 per month (gross base salary), paid on a 14-month basis")
    rates, _ = fx_rates()
    assert pay.min_usd == round(4116 * 12 * rates["EUR"])
    assert "monthly ×12" in pay.note and "EUR at" in pay.note


def test_hourly_is_annualized():
    pay = _detail("Pay: $45.00 - $55.00 per hour, depending on experience")
    assert (pay.min_usd, pay.max_usd) == (93600, 114400)
    assert "hourly ×2080" in pay.note


def test_single_figure_is_used_as_midpoint():
    pay = _detail("Base salary: $150,000 plus equity")
    assert (pay.min_usd, pay.max_usd, pay.mid_usd) == (150000, 150000, 150000)
    assert pay.note.startswith("text, single figure")


@pytest.mark.parametrize("line", [
    "Manage enterprise opportunities typically valued at $60K+ ACV, including six-figure deals.",
    "We manage $110+ billion in loans across 50 states.",
    "5-7+ years in product operations with a $2M budget",
    "Expected travel 10-20% to client sites",
    "Base Salary Range: $12,000 and $15,000",  # below the annual floor: a parse error, not pay
])
def test_business_figures_and_noise_are_not_pay(line):
    assert extract_posted_pay(f"<p>{line}</p>") == (0, 0, 0)


def test_unsupported_currency_is_left_for_the_bls_fallback():
    assert extract_posted_pay("<p>Salary range: A$150,000 - A$180,000</p>") == (0, 0, 0)
