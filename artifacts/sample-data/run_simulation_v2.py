import csv, re, sys

LEGACY_REQUIRED = {'PersonId': 'Email', 'EffectiveDate': 'DateTime', 'ManagerId': 'Email', 'Organization': 'String'}
MODIS_REQUIRED = {'Microsoft_PersonEmail': 'Email', 'Microsoft_ManagerEmail': 'Email', 'Microsoft_Organization': 'String'}
MODIS_MAP = {
    'PersonId': 'Microsoft_PersonEmail', 'ManagerId': 'Microsoft_ManagerEmail',
    'Organization': 'Microsoft_Organization', 'FunctionType': 'Microsoft_JobDiscipline',
    'Location': 'Microsoft_CompanyOfficeLocation', 'HireDate': 'Microsoft_HireDate',
    'HourlyRate': 'Microsoft_HourlyRate', 'LevelDesignation': 'Microsoft_LevelDesignation',
    'EffectiveDate': '(remove — use UI date picker)',
}
RESERVED = {
    'FunctionType': 'String', 'LevelDesignation': 'String', 'HireDate': 'DateTime',
    'HourlyRate': 'Double', 'Layer': 'Integer', 'SupervisorIndicator': 'String',
    'WeeklyBadgeOnsiteDays': 'Double', 'Location': 'String', 'CountryOrRegion': 'String'
}
FORBIDDEN = ['TimeZone','Domain','PopulationType','StartDate','EndDate','ObjectId',
             'IsActive','MetricDate','StandardTimeZone','WorkdayStart','WorkDayEnd',
             'WeekendDays','InferredTeamSize']
SENTINEL = ['#N/A','N/A','NULL','null','none','n/a','NA']
SF_INDICATORS = ['userId','jobCode','businessUnit','employmentNav','costCenter']
WD_INDICATORS = ['Worker_ID','Supervisory_Organization','Cost_Center_Reference','Management_Level']

def detect_path(headers):
    has_modis = any(h.startswith('Microsoft_') for h in headers)
    has_legacy = 'PersonId' in headers or 'ManagerId' in headers
    if has_modis: return 'MODIS'
    if has_legacy: return 'LEGACY'
    return 'UNKNOWN'

def is_code_like(values):
    """Check if values look like system codes rather than readable names"""
    if not values: return False
    code_count = 0
    for v in values:
        if re.match(r'^[A-Z]{1,4}-?\d+$', v) or re.match(r'^\d+$', v) or len(v) < 3:
            code_count += 1
    return code_count > len(values) * 0.5

def detect_hris(headers, rows):
    h_lower = [h.lower() for h in headers]
    if any(ind.lower() in h_lower for ind in SF_INDICATORS):
        return 'SAP SuccessFactors'
    if any(ind.lower() in h_lower for ind in WD_INDICATORS):
        return 'Workday'
    return None

def validate(fp, label, target_path=None):
    sep = "=" * 80
    print(f"\n{sep}")
    print(f"  {label}")
    print(f"  File: {fp}")
    print(sep)

    with open(fp) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    pid_col = 'PersonId' if 'PersonId' in headers else 'Microsoft_PersonEmail' if 'Microsoft_PersonEmail' in headers else None
    mgr_col = 'ManagerId' if 'ManagerId' in headers else 'Microsoft_ManagerEmail' if 'Microsoft_ManagerEmail' in headers else None
    org_col = 'Organization' if 'Organization' in headers else 'Microsoft_Organization' if 'Microsoft_Organization' in headers else None

    pids = set(r[pid_col].strip() for r in rows if pid_col and r.get(pid_col,'').strip()) if pid_col else set()
    mids = set(r[mgr_col].strip() for r in rows if mgr_col and r.get(mgr_col,'').strip()) if mgr_col else set()
    orphans = mids - pids
    all_pids = [r[pid_col].strip() for r in rows] if pid_col else []
    dup_count = len(all_pids) - len(set(all_pids)) if all_pids else 0
    forbidden_found = [h for h in headers if h in FORBIDDEN]

    # 1. File Summary + Path Detection
    detected_path = detect_path(headers)
    effective_path = target_path if target_path else detected_path

    print(f"\n## 1. FILE SUMMARY")
    print(f"  Rows: {len(rows)}, Columns: {len(headers)}")
    print(f"  Unique employees: {len(pids)}, Duplicates: {dup_count}")
    print(f"  Upload path detected: {detected_path}")
    if target_path and target_path != detected_path:
        print(f"  TARGET path: {target_path} — MISMATCH with file schema!")
        print(f"\n  COLUMN RENAME MAPPING (Legacy → MODIS):")
        print(f"  {'Legacy Name':<25} {'M365 Admin Centre Name':<35} Action")
        print(f"  {'─'*25} {'─'*35} {'─'*10}")
        for old, new in MODIS_MAP.items():
            if old in headers:
                action = "Delete column" if 'remove' in new else "Rename"
                print(f"  {old:<25} {new:<35} {action}")
    print(f"  Forbidden columns: {forbidden_found if forbidden_found else 'None'}")
    print(f"  Total attributes: {len(headers)}/105 max")

    # HRIS detection
    hris = detect_hris(headers, rows)
    if hris:
        print(f"\n  HRIS DETECTED: {hris}")
        print(f"  → Consider using the native M365 {hris} connector instead of CSV upload.")

    # 1b. Attribute Completeness
    print(f"\n## 1b. ATTRIBUTE COMPLETENESS")
    print(f"  {'Column':<30} {'Filled':<10} {'Total':<8} {'%':<8} Quality")
    print(f"  {'─'*30} {'─'*10} {'─'*8} {'─'*8} {'─'*10}")
    for col in headers:
        filled = sum(1 for r in rows if r[col].strip() and r[col].strip() not in SENTINEL)
        pct = filled / len(rows) * 100 if rows else 0
        if pct == 0: quality = "EMPTY"
        elif pct < 50: quality = "POOR"
        elif pct < 95: quality = "LOW"
        else: quality = "GOOD"
        print(f"  {col:<30} {filled:<10} {len(rows):<8} {pct:<7.0f}% {quality}")

    # 2. Required Attributes
    print(f"\n## 2. REQUIRED ATTRIBUTES")
    req_cols = LEGACY_REQUIRED if detected_path != 'MODIS' else MODIS_REQUIRED
    for attr, dtype in req_cols.items():
        if attr in headers:
            filled = sum(1 for r in rows if r[attr].strip())
            pct = filled / len(rows) * 100
            if attr in (mgr_col,):
                blanks = sum(1 for r in rows if not r[attr].strip())
                status = "PASS" if blanks <= 1 else f"WARNING ({blanks} blank)"
            elif pct == 100: status = "PASS"
            elif pct == 0: status = "CRITICAL FAIL (0%)"
            else: status = f"FAIL ({pct:.0f}%)"
            print(f"  {attr}: {filled}/{len(rows)} ({pct:.0f}%) → {status}")
        else:
            print(f"  {attr}: MISSING → CRITICAL FAIL")

    # Hierarchy check
    if pid_col and mgr_col:
        print(f"  Hierarchy: {len(orphans)}/{len(mids)} managers NOT in {pid_col} list")
        if orphans:
            if len(orphans) == len(mids) and len(mids) > 0:
                print(f"    ⚠ NO managers exist as employees → hierarchy CANNOT BUILD")
                print(f"    Loop detection: NOT APPLICABLE (hierarchy doesn't exist)")
            elif len(orphans) <= 5:
                print(f"    Orphaned: {list(orphans)}")
            else:
                print(f"    Orphaned (first 5): {list(orphans)[:5]}...")

    # Code-like Organization check
    if org_col and org_col in headers:
        org_vals = list(set(r[org_col].strip() for r in rows if r[org_col].strip()))
        if org_vals and is_code_like(org_vals):
            print(f"  ⚠ Organization values appear CODE-LIKE: {org_vals[:5]}")
            print(f"    Dashboard will show codes instead of readable names. Map to human-readable labels.")

    # 3. Reserved Attributes
    print(f"\n## 3. RESERVED ATTRIBUTES")
    for attr, dtype in RESERVED.items():
        if attr in headers:
            vals = [r[attr].strip() for r in rows if r[attr].strip()]
            uniq = set(vals)
            filled_pct = len(vals) / len(rows) * 100
            issues = []
            if dtype == 'Integer':
                non_int = [v for v in uniq if not v.lstrip('-').isdigit()]
                if non_int: issues.append(f"NON-INTEGER: {list(non_int)[:5]}")
            elif dtype == 'Double':
                non_dbl = [v for v in uniq if not re.match(r'^-?\d+\.?\d*$', v)]
                if non_dbl: issues.append(f"INVALID format: {list(non_dbl)[:5]}")
                has_symbols = [v for v in uniq if '$' in v or ',' in v]
                if has_symbols: issues.append(f"Has $/commas (strip before upload): {list(has_symbols)[:3]}")
            elif dtype == 'DateTime':
                sents = [v for v in uniq if v in SENTINEL or v.startswith('0/')]
                placeholders = [v for v in uniq if '1900' in v or '1970' in v or '9999' in v]
                if sents: issues.append(f"SENTINEL/INVALID: {sents}")
                if placeholders: issues.append(f"PLACEHOLDER dates: {list(placeholders)[:3]}")
            status = "PASS" if not issues else "FAIL"
            extra = ""
            if attr == 'HourlyRate' and vals:
                extra = " | ⚠ Set to CONFIDENTIAL access during upload"
            print(f"  {attr}: {len(vals)}/{len(rows)} ({filled_pct:.0f}%), {len(uniq)} unique → {status}{extra}")
            for iss in issues:
                print(f"    ! {iss}")
        else:
            print(f"  {attr}: not present")

    # 4. Data Quality
    print(f"\n## 4. DATA QUALITY ISSUES")
    issue_count = 0
    # Sentinels (with row numbers)
    sentinel_found = {}
    for col in headers:
        for i, r in enumerate(rows):
            v = r[col].strip()
            if v in SENTINEL:
                issue_count += 1
                print(f"  [{issue_count}] SENTINEL row {i+2}: {col} = '{v}' (NOT blank — distinct invalid string)")
                sentinel_found.setdefault(col, []).append(i+2)
    # Empty columns
    empty_cols = [h for h in headers if all(not r[h].strip() for r in rows)]
    if empty_cols:
        issue_count += 1
        print(f"  [{issue_count}] 100% EMPTY columns ({len(empty_cols)}): {empty_cols}")
    # Parenthetical IDs
    paren_cols = [h for h in headers if any(re.search(r'\(\d{3,}\)', r[h]) for r in rows)]
    if paren_cols:
        issue_count += 1
        print(f"  [{issue_count}] PARENTHETICAL IDs in: {paren_cols} — strip for cleaner dashboard labels")
    # Date format
    for dc in [h for h in headers if 'date' in h.lower() or h == 'EffectiveDate']:
        vals = [r[dc].strip() for r in rows if r[dc].strip() and r[dc].strip() not in SENTINEL and not r[dc].strip().startswith('0/')]
        if vals:
            has_slash = any('/' in v for v in vals)
            has_dash = any(v[0].isdigit() and '-' in v for v in vals)
            if has_slash and has_dash:
                issue_count += 1
                print(f"  [{issue_count}] MIXED date formats in {dc} — some use / some use -")
            elif has_dash:
                issue_count += 1
                print(f"  [{issue_count}] {dc}: YYYY-MM-DD format — select DateTime_MMDDYYYY during upload")
            elif has_slash:
                sample = vals[0]
                parts = sample.split('/')
                if len(parts) == 3:
                    try:
                        d1, d2 = int(parts[0]), int(parts[1])
                        if d1 > 12:
                            issue_count += 1
                            print(f"  [{issue_count}] {dc}: DD/MM/YYYY detected — select DateTime_DDMMYYYY during upload")
                        elif d2 > 12:
                            issue_count += 1
                            print(f"  [{issue_count}] {dc}: MM/DD/YYYY detected — select DateTime_MMDDYYYY during upload")
                        else:
                            issue_count += 1
                            print(f"  [{issue_count}] {dc}: AMBIGUOUS date format (sample: {sample}) — could be MM/DD or DD/MM. Confirm with data owner.")
                    except ValueError:
                        pass
    # Duplicates
    if dup_count > 0:
        from collections import Counter
        dupes = [k for k, v in Counter(all_pids).items() if v > 1]
        issue_count += 1
        print(f"  [{issue_count}] DUPLICATE PersonIds: {dupes}")
    # Forbidden
    if forbidden_found:
        issue_count += 1
        print(f"  [{issue_count}] FORBIDDEN system columns: {forbidden_found} — upload WILL FAIL")
    # Non-email managers
    if mgr_col and mgr_col in headers:
        non_email_mgrs = set()
        for r in rows:
            m = r[mgr_col].strip()
            if m and '@' not in m:
                non_email_mgrs.add(m)
        if non_email_mgrs:
            issue_count += 1
            print(f"  [{issue_count}] NON-EMAIL ManagerIds: {list(non_email_mgrs)[:5]} — must be email addresses, not display names")
    if issue_count == 0:
        print(f"  No issues found.")

    # 8. Dashboard Impact
    print(f"\n## 8. DASHBOARD IMPACT ASSESSMENT")
    org_ok = org_col and org_col in headers and any(r[org_col].strip() for r in rows)
    func_col = 'FunctionType' if 'FunctionType' in headers else 'Microsoft_JobDiscipline' if 'Microsoft_JobDiscipline' in headers else None
    func_ok = func_col and any(r[func_col].strip() for r in rows)
    hier_ok = len(orphans) < len(mids) * 0.5 if mids else False
    hr_col = 'HourlyRate' if 'HourlyRate' in headers else 'Microsoft_HourlyRate' if 'Microsoft_HourlyRate' in headers else None
    hr_ok = hr_col and any(r[hr_col].strip() for r in rows)

    print(f"\n  | Dashboard Element | Status | Impact |")
    print(f"  |---|---|---|")
    print(f"  | Organization filter | {'✅ WILL WORK' if org_ok else '❌ WILL NOT APPEAR'} | {'Segment by business unit' if org_ok else 'No org comparison available'} |")
    print(f"  | Job Function filter | {'✅ WILL WORK' if func_ok else '❌ WILL NOT APPEAR'} | {'Segment by role' if func_ok else 'No role comparison (no Entra fallback)'} |")
    print(f"  | Scope/Group view | {'✅ WILL WORK' if hier_ok else '❌ BROKEN'} | {'Leaders see their teams' if hier_ok else 'Only Your company visible — no drilldown'} |")
    print(f"  | Assisted Value (ROI) | {'✅ Custom rate' if hr_ok else '⚠ Default $72/hr'} | {'Org-specific ROI' if hr_ok else 'Generic ROI — may be inaccurate'} |")

    if org_ok:
        org_vals = set(r[org_col].strip() for r in rows if r[org_col].strip())
        print(f"\n  Dashboard Preview — Organization filter values ({len(org_vals)}):")
        for v in sorted(org_vals): print(f"    • {v}")
    if func_ok:
        func_vals = set(r[func_col].strip() for r in rows if r[func_col].strip())
        print(f"  Dashboard Preview — Job Function filter values ({len(func_vals)}):")
        for v in sorted(func_vals): print(f"    • {v}")

    # Grade
    critical = 0
    if not org_ok and org_col and org_col in headers: critical += 1
    if not pid_col or pid_col not in headers: critical += 1
    if not mgr_col or mgr_col not in headers: critical += 1
    if detected_path == 'UNKNOWN': critical += 1
    if not hier_ok and mids: critical += 1
    if forbidden_found: critical += 1
    if dup_count > 0: critical += 1
    has_non_email = mgr_col and mgr_col in headers and any(r[mgr_col].strip() and '@' not in r[mgr_col].strip() for r in rows)
    if has_non_email: critical += 1

    if target_path and target_path != detected_path:
        critical += 1  # schema mismatch

    if critical == 0 and issue_count <= 2:
        grade = "A — Upload-ready"
    elif critical == 0:
        grade = "B — Minor fixes needed"
    elif critical <= 2:
        grade = "C — Significant fixes required"
    else:
        grade = "D — Major rework required"

    print(f"\n  OVERALL GRADE: {grade}")
    print(f"  Critical: {critical} | Total issues: {issue_count}")
    if target_path and target_path != detected_path:
        print(f"  ⚠ SCHEMA MISMATCH: File uses {detected_path} names but target is {target_path}")
        print(f"    Apply the Column Rename Mapping above before upload.")

datasets = [
    ('artifacts/sample-data/sim1_good.csv', 'SIM 1: GOOD DATA (Fabrikam)', None),
    ('artifacts/sample-data/sim2_partial.csv', 'SIM 2: PARTIALLY GOOD (Tailspin Toys)', None),
    ('artifacts/sample-data/sim3_bad.csv', 'SIM 3: MAJOR IMPROVEMENTS (Litware)', None),
    ('artifacts/sample-data/sim4_modis_legacy.csv', 'SIM 4: MODIS TARGET w/ LEGACY DATA (Wingtip)', 'MODIS'),
]
for fp, label, tp in datasets:
    validate(fp, label, tp)

print(f"\n{'='*80}")
print("  ALL SIMULATIONS COMPLETE")
print(f"{'='*80}")
