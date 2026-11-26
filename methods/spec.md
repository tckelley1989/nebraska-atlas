# Methods spec

Every measure in the Atlas follows these rules. A new measure inherits them; a measure that needs an exception gets it written here first, then in the registry.

Written November 25, 2026 from the rules the v1 pipeline (`nebraska-economy`) runs today and the v1 About page. Where a rule lives in code, the file is named.

## 1. Counting and dividing

1. Tier, crop-district and statewide figures sum counts first and divide last. They never average county or system rates.
2. "All counties" is the sum of the 93 counties. Jobs BLS assigns to no county are reported beside it, not inside it.
3. Statewide school figures sum every certified system, including systems later merged.
4. Three student counts are in use, because the sources use them. Each measure names its count in the registry `unit` and `note`:
   - **Formula students:** TEEOSA's count for the aid year (Neb. Rev. Stat. 79-1003). Every certification measure.
   - **Average daily membership (ADM):** where students attend, as NDE counts for per pupil cost. Money received and per pupil cost.
   - **Students living in a county (estimate):** each district split by where its 2020 Census children ages 5 to 17 live. County school measures.

## 2. Base periods and real dollars

1. Change measures run from the base period in the registry `base_period` column to the latest period: 2019 for calendar and tax years, 2019-20 for school and aid years. Exceptions are written in the registry (net migration from 2020; farm sales from the 2017 Census of Agriculture).
2. Real dollars use the Midwest CPI-U with 2019 as the base:
   - calendar-year average for economic and property tax data
   - September to August average for school years; an unfinished school year uses the latest 12 published months
   - school adjusted valuation and taxable valuation are deflated by the CPI of their calendar year
3. BEA's state and local government consumption price index is the robustness check. Both deflators are published in `deflators.csv`.
4. Tax years and school years are kept apart. Tax year Y is levied in fall Y and paid inside school fiscal year Y. Neither is subtracted from the other.

## 3. Small bases and reliability

Each rule below is a registry column, so the build applies it without page code.

| Rule | Registry value | Applies to | What the reader sees |
|---|---|---|---|
| Small base | `small_base_field`, `small_base_min` | Payroll job and wage change (under 1,000 payroll jobs); population change and net migration (under 1,000 residents) | Value shown with the `small_n_note` caution |
| Survey margin of error | `acs_cv_over_30_greyed` | ACS income, poverty, education, broadband | Greyed and marked unreliable when the coefficient of variation is over 30%. ACS changes compare 2015-2019 with 2020-2024 and are called significant only at 90% confidence. ACS medians and percents get no tier or all-county value |
| Minimum system size | `min_1000_formula_students` | Matched-cohort growth | Shown only for systems of 1,000 or more formula students. Below that, year-to-year rank correlation is 0.09 at 500+, 0.24 at 1,000+, 0.46 at 3,000+ (`indicators_nep.py`) |
| Agency suppression | `nde_suppression_kept_blank` | NDE outcome and teacher measures | Blank with the missing label |

Values an agency withholds are never estimated and never shown as zero.

## 4. NSCAS results

Source: `_totals()` and `nscas` year selection in `pipeline/indicators_nep.py`; the audit applies the same rule independently in `audit/transforms/40_schools.sql`.

NDE stopped publishing all-grades NSCAS rows with its 2025-26 Education Profile release (November 25, 2026), and kept grade rows. NDE withholds a grade's counts when the group is small or its percent is extreme: every grade it shows has an on-track share between 20% and 82%. So the grades left over are not a fair sample of the system.

1. Proficiency and the subgroup gaps use NDE's own all-grades totals, from the latest year NDE published them (2024-25), labeled with that year. They move to 2025-26 when NDE publishes 2025-26 totals.
2. Where NDE published an all-grades count, it is used as published; a withheld count stays withheld. Only a count NDE did not publish is summed from grades 3 to 8.
3. Summing the grades NDE did show was tested against NDE's 2024-25 totals and rejected: keeping systems with up to 10% of students withheld reaches 44 systems for mathematics, with errors up to 7.3 points.
4. Percents are computed from the counts. NDE's own percent columns are not read.
5. The scale score against the state uses 2024-25, the proficiency year, and growth uses 2025-26 grade rows. Both compare, for grades 3 to 8, the system's grade average with the state's, weighted by the system's tested counts. For the scale score, a withheld grade count is what is left of NDE's all-grades count after the published grades and grade 11. Grade 11 can be no larger than the statewide grade 11 count less every published one. Where every count is published but a score is withheld, NDE's all-grades average gives the grades 3 to 8 average exactly when no grade 11 student is left over. A system is shown when these bounds pin its value within 1 point either way: 119 systems against 14 when any withheld grade blanked it. The identity held within 0.5 points in 29 of 30 checkable systems (one NDE row is off by 7.5). Growth still blanks a withheld grade cell and is shown only for systems of 1,000 or more formula students.

Coverage with NDE's 2024-25 totals: mathematics 221 of 244 systems, English language arts 235, science 121.

## 5. Deeper dive

Source: `scripts/atlas/dive.py` (computed and drawn at build) and `templates/dive.js` (the selected place). One page per measure, `dive/<level>/<key>.html`, in five steps: what's normal, kind of place, why by design, what else goes with it, up close.

1. Every pair of measures is ranked by Spearman rank correlation.
2. Significance: Fisher z with the Spearman variance correction, 1.06 / (n − 3), two-sided normal p.
3. Holm correction at 5% across every measure tested against the one on the page. A result that survives is "stronger than chance"; the rest "could be chance".
4. Within-group check: ranks are demeaned inside each tier (counties) or size band (systems: under 200, 200 to 499, 500 to 999, 1,000 to 4,999, 5,000+). If the within-group correlation falls below half the overall one, the page says the pattern is mostly a gap between groups.
5. Pairs in the same family (`registry/families.csv`, the source of truth) are not tested. They are listed under step 3, because they move together by arithmetic.
6. Mechanism before correlation: step 3 states the arithmetic from `registry/mechanisms.csv`. The TEEOSA formula (family s01) and the property tax identity (family c07) get a chart; other families get their one-line reason.
7. Sort order: results that hold come first, strongest first, then the rest. A result that does not hold never sits above one that does.
8. Minimum count: a pair needs at least half the places (122 systems or 47 counties). Pairs below it are listed as too few to test.
9. Every result that holds gets a why line. A mechanism is stated only where arithmetic links the pair: the TEEOSA formula (aid against school adjusted or taxable valuation per student, only when the sign is negative as the formula predicts), the levy (the request divided by taxable valuation, so a levy page states each partner's own rank correlation with taxable valuation per student and counts a link only at 0.3 or more in size), and the three property tax factors for county tax measures. Every other result reads "No formula link" with its own correlation and is called an association. "A board's levy does not change its aid" appears only on TEEOSA aid per student. Levies are tagged "Board sets" and unused authority "Board choice". A test of these rules runs on every page: each holding result is named, each with/against agrees with the sign beside it, and each mechanism line has its arithmetic link. A measure reported by fewer than half the places says so in place of a test count.
10. Step 5 opens on the strongest result that holds; up to four scatters are drawn. The five places furthest from the line are labeled, labels never overlap, and the selected place is always labeled.
11. Axes: a measure with a long upper tail is cut at its 99th percentile, with the places above drawn as arrows at the edge. A measure whose values all sit far above zero starts at a round number below its minimum, with a break mark.
12. Strength words: under 0.1 negligible, 0.1 to 0.3 weak, 0.3 to 0.5 moderate, 0.5 or more strong.
13. The selected place's formula lines (need, resources, equalization, total aid) are generated from certification fields and tested against the certified total for every system; the property tax identity is tested against the published measure for every county.

## 6. Estimates

Labeled estimates, with their tested error, published on the About page and recomputed every build:

| Estimate | Method | Tested error |
|---|---|---|
| County splits of school students, aid and money | District split by 2020 Census children ages 5 to 17 | 5.6% of taxable valuation placed in the wrong county across the 200 districts that cross county lines (worst district 36%) |
| County real property credits, tax years 2019 to 2021 | Statewide rates applied to county value | 0.4% median, 5.9% worst, tested on certified years 2022 to 2025 |
| LB 1107 credits | Revenue's all-filer totals, split by Revenue's own school and community college split, then by tax base | Untestable assumption: owners claim at the same rate everywhere |

## 7. Preliminary figures and revisions

1. Agencies' own preliminary flags are used where they exist (LAUS, current crop insurance year).
2. Otherwise the rule is fixed in advance: the four latest QCEW quarters, the latest BEA county income year and the latest year of the newest Census population vintage are preliminary.
3. A build that changes no published value stores nothing. Otherwise every changed value is logged in `revisions.csv` with both build dates.

## 8. Maps and color

1. Color breaks are fixed in the registry, so a place changes color only when its data changes.
2. Every map uses exactly one ramp, shows its legend on screen, and labels the selected place with the charcoal-and-card outline.
3. Every change number carries a + or − sign in text, tiles and tables.
4. Bin count equals the registry `breaks` count plus one, and must match the ramp's step count. The test gate checks this.
5. A percent change of +200% or more (three times the base) is shown as the multiple, "12.4 times", in tiles, tables and text. From a small base a percent that large misleads: a system that got $84 per student in 2019-20 and $3,306 now is "39.3 times", not "+3,835.7%". Downloads keep the raw percent, and map colors are unchanged, since those values already fall in the top bin. Declines are bounded at −100% and always show as percents. Source: `fmt.pct_change()`.
6. Each map has a table view with the same values: every place, ranked and sortable, blanks last. Its values must equal the map's, place for place (`test_map_table_has_every_place_and_matches_the_map`).
7. A map download (PNG or SVG) draws the title, legend with counts, the not-available hatch, period and source into the file, so it stands on its own outside the site.

## 9. School receipts and the state share

1. Money received is what each district reported in its Annual Financial Report from 2018-19 on, for the taxpayer-supported funds (general, depreciation, employee benefit, contingency, bond, special building, qualified capital purpose, cooperative).
2. NDE's standard state share is state sources over the four General Fund receipt totals, as reported.
3. "Credits counted as local" moves property tax credits (03131) and homestead exemption reimbursement (03130) paid by the state back to local, since both pay part of a tax the school board levies.
4. The LB 1107 income tax credit claimed against school taxes, booked by districts as local taxes, is moved to state, split by each district's property tax receipts outside the bond fund (an estimate).
5. Federal money is shown but kept out of the state share.
6. Tax year 2023 is LB 34's missing year. Its school taxes were paid in 2024 and claimed in income tax year 2024, when the credit covers community college taxes only. The School District Property Tax Relief Credit starts with tax year 2024 statements. So school taxes levied in 2023 and paid after Jan. 2, 2024 got neither credit, and the LB 1107 school credit for 2023-24 is $0 by rule, not missing data. It is not zero school relief, since the Property Tax Credit Act credit still applied. 2023 taxes paid by Jan. 2, 2024 could claim the old credit in income tax year 2023, and they are counted with tax year 2022.
7. The Statewide picture splits the rise in the reported state share into credits, homestead reimbursement and all other state money. General Fund homestead reimbursement is not published on its own (the bundle's homestead figure covers all funds), so it is the gap between the two shares, in dollars, less credits. The three parts add to the rise (`test_statewide_picture`).

## Open items for v2

None. Closed November 25, 2026:

- The percent-change floor is rule 8.5.
- Tier figures in Findings follow rule 1.1: every tier change it quotes equals its counties' summed levels (`test_tier_changes_sum_counts_first`), and none matches the median county. v2 shows no median county in Findings, so v1's "median county" note has no counterpart. Medians appear only on profile tiles, labeled "Median".
