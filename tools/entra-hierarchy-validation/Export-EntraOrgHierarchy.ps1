#Requires -Modules Microsoft.Graph.Authentication, Microsoft.Graph.Users
<#
.SYNOPSIS
  Export the Microsoft Entra ID user + manager reporting hierarchy to CSV so it can
  be validated for Copilot Dashboard "Scope" rollup problems.

.DESCRIPTION
  When NO organizational data file has been uploaded, the Microsoft Copilot Dashboard
  builds its "Your company" / "Your group" Scope rollups directly from the Microsoft
  Entra ID manager hierarchy (the "ManagerID" attribute). In that mode the Entra
  manager chain IS the dashboard hierarchy.

  This script extracts that chain to a CSV using column names that line up with the
  Viva Insights organizational-data fields. Validate the resulting CSV downstream with
  the Microsoft 365 Copilot Analyst Agent (use the Org Data Validation prompt), and, if
  needed, adapt it into an org-data upload later.

  Output columns (one row per enabled member by default):
    PersonId            - userPrincipalName            (maps to Viva Insights "PersonId")
    DisplayName         - displayName
    Mail                - mail
    ManagerId           - manager's userPrincipalName  (maps to Viva Insights "ManagerId")
    ManagerDisplayName  - manager's displayName
    Organization        - department                   (maps to Viva Insights "Organization")
    JobTitle            - jobTitle
    CompanyName         - companyName
    AccountEnabled      - accountEnabled

.PARAMETER OutputPath
  Path to the CSV to write. Default: entra-org-hierarchy.csv in the current directory.

.PARAMETER IncludeDisabled
  Include accounts where accountEnabled = false. By default only enabled accounts are
  exported (the dashboard reports on licensed/active members).

.PARAMETER UsePerUserManagerLookup
  Use a per-user Get-MgUserManager call instead of $expand=manager. Slower on large
  tenants but maximally reliable if the expanded manager UPN ever comes back blank.

.PARAMETER TenantId
  Optional Microsoft Entra tenant ID to sign in against. If omitted, the default
  tenant for the chosen app/sign-in is used.

.PARAMETER ClientId
  Optional app registration (client) ID to authenticate with. If omitted, the built-in
  Microsoft Graph PowerShell app is used. The app must have the delegated User.Read.All
  permission and (for device code) public client flows enabled.

.PARAMETER UseDeviceCode
  Authenticate using the device code flow: a code + URL is printed and you complete
  sign-in in a browser. Useful for headless terminals.

.NOTES
  Least-privilege Graph permission: User.Read.All (admin consent may be required).
  Get-MgUser:        https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.users/get-mguser
  Get-MgUserManager: https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.users/get-mgusermanager

.EXAMPLE
  ./Export-EntraOrgHierarchy.ps1
  Exports all enabled users and their managers to entra-org-hierarchy.csv.

.EXAMPLE
  ./Export-EntraOrgHierarchy.ps1 -OutputPath C:\temp\hierarchy.csv -UsePerUserManagerLookup
#>

[CmdletBinding()]
param(
    [string] $OutputPath = "entra-org-hierarchy.csv",
    [switch] $IncludeDisabled,
    [switch] $UsePerUserManagerLookup,
    [string] $TenantId,
    [string] $ClientId,
    [switch] $UseDeviceCode,
    [switch] $ForceConnect
)

$ErrorActionPreference = 'Stop'

# Reuse an existing Microsoft Graph connection when one with a sufficient scope is
# already established (e.g. you ran Connect-MgGraph once in a persistent session).
# This avoids re-authenticating per process, which is where device-code flows break.
$existing = $null
try { $existing = Get-MgContext } catch { }
$haveScope = $existing -and (
    ($existing.Scopes -contains 'User.Read.All') -or
    ($existing.Scopes -contains 'Directory.Read.All')
)

if ($haveScope -and -not $ForceConnect) {
    Write-Host ("Reusing existing Microsoft Graph connection: {0}" -f $existing.Account) -ForegroundColor DarkGray
}
else {
    # Connect with the minimum scope needed to read users and their manager.
    # TenantId / ClientId / UseDeviceCode are added only when supplied.
    $connect = @{ Scopes = 'User.Read.All'; NoWelcome = $true }
    if ($TenantId)      { $connect.TenantId      = $TenantId }
    if ($ClientId)      { $connect.ClientId      = $ClientId }
    if ($UseDeviceCode) { $connect.UseDeviceCode = $true }
    Connect-MgGraph @connect
}

# Properties to retrieve (mapped to Viva Insights fields in the output below).
$select = @(
    'id','userPrincipalName','displayName','mail',
    'accountEnabled','department','jobTitle','companyName'
)

Write-Host "Retrieving users from Microsoft Entra ID..." -ForegroundColor Cyan

if ($UsePerUserManagerLookup) {
    $users = Get-MgUser -All -Property $select -PageSize 999
}
else {
    # Expand the manager and select the manager's UPN in the same paged call (efficient).
    # The backtick before $select stops PowerShell from interpolating it; Graph receives it literally.
    $users = Get-MgUser -All -Property $select `
        -ExpandProperty "manager(`$select=id,userPrincipalName,displayName)" -PageSize 999
}

Write-Host ("Retrieved {0} users. Resolving managers..." -f $users.Count) -ForegroundColor Cyan

$rows = foreach ($u in $users) {

    if (-not $IncludeDisabled -and $u.AccountEnabled -ne $true) { continue }

    $mgrUpn  = $null
    $mgrName = $null

    if ($UsePerUserManagerLookup) {
        try {
            $mgr = Get-MgUserManager -UserId $u.Id -ErrorAction Stop
            if ($mgr) {
                $mgrUpn  = $mgr.AdditionalProperties['userPrincipalName']
                $mgrName = $mgr.AdditionalProperties['displayName']
            }
        }
        catch {
            # 404 = user has no manager assigned -> treat as a root candidate.
        }
    }
    elseif ($u.Manager) {
        $mgrUpn  = $u.Manager.AdditionalProperties['userPrincipalName']
        $mgrName = $u.Manager.AdditionalProperties['displayName']

        # Belt-and-suspenders: if the expand didn't surface the manager's UPN but we
        # have the manager's object id, resolve it with a single targeted lookup.
        if (-not $mgrUpn -and $u.Manager.Id) {
            try {
                $mgrObj  = Get-MgUser -UserId $u.Manager.Id -Property userPrincipalName,displayName -ErrorAction Stop
                $mgrUpn  = $mgrObj.UserPrincipalName
                $mgrName = $mgrObj.DisplayName
            }
            catch { }
        }
    }

    [pscustomobject]@{
        PersonId           = $u.UserPrincipalName
        DisplayName        = $u.DisplayName
        Mail               = $u.Mail
        ManagerId          = $mgrUpn
        ManagerDisplayName = $mgrName
        Organization       = $u.Department
        JobTitle           = $u.JobTitle
        CompanyName        = $u.CompanyName
        AccountEnabled     = $u.AccountEnabled
    }
}

$rows | Sort-Object PersonId | Export-Csv -Path $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host ("Exported {0} rows to {1}" -f $rows.Count, $OutputPath) -ForegroundColor Green
Write-Host "Next: validate this CSV with the Microsoft 365 Copilot Analyst Agent (Org Data Validation prompt)." -ForegroundColor Yellow
