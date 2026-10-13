# O*NET database attribution

The occupation classification experiment uses the **O*NET 31.0 Database** from
the **U.S. Department of Labor, Employment and Training Administration
(USDOL/ETA)**, available at <https://www.onetcenter.org/database.html>.

The source database is licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
See the publisher's [database licence information](https://www.onetcenter.org/license_db.html).

CareerLens groups selected occupation codes into broader categories, normalizes
and filters records, removes duplicate or conflicting groups, samples negative
examples, creates evaluation splits, and trains classification weights. These
changes and the resulting model have not been approved, endorsed, or tested by
USDOL/ETA. The source occupation labels should not be described as labels for
job advertisements.

O*NET® is a trademark of USDOL/ETA. Source CSVs and trained weights are generated
local artifacts and are not included in this repository. File versions and
checksums are recorded in `backend/ml/role_data.py` and
`evaluation/role-results.json`. Retain this attribution when distributing the
derived data or weights.
