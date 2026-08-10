[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $repositoryRoot 'map-config.json'

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'map-config.json is missing.'
}

$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($null -eq $manifest.layers) {
    throw 'map-config.json must contain a layers array. The array may be empty for symbology mode.'
}

$missing = [System.Collections.Generic.List[string]]::new()
$invalidGeoJson = [System.Collections.Generic.List[string]]::new()
$basemapUrls = @($manifest.basemaps.url)
$environmentalUrls = [System.Collections.Generic.List[string]]::new()
foreach ($analysis in @($manifest.environmental_health.analyses)) {
    if ($analysis.overview_url) { $environmentalUrls.Add([string] $analysis.overview_url) }
    foreach ($year in @($manifest.environmental_health.years)) {
        if ($analysis.timeline_url) {
            $environmentalUrls.Add(([string] $analysis.timeline_url).Replace('{year}', [string] $year))
        }
    }
}
$repositoryUrls = @($manifest.layers.url) + @($manifest.satellite_assets.url) + @($environmentalUrls)
$externalUrls = @($repositoryUrls | Where-Object { $_ -match '^https?://' } | Sort-Object -Unique)

if ($externalUrls.Count) {
    Write-Error ("External project-data URLs are not allowed. Copy these resources into the repository:`n - " + ($externalUrls -join "`n - "))
    exit 1
}

$localBasemapUrls = @($basemapUrls | Where-Object { $_ -and $_ -notmatch '^https?://' })
$localUrls = $repositoryUrls + $localBasemapUrls
foreach ($url in ($localUrls | Where-Object { $_ } | Sort-Object -Unique)) {
    $normalizedUrl = [System.Uri]::UnescapeDataString([string] $url).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $target = Join-Path $repositoryRoot $normalizedUrl
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $missing.Add([string] $url)
        continue
    }
    if ([System.IO.Path]::GetExtension($target) -ieq '.geojson') {
        try {
            $geoJson = Get-Content -Raw -LiteralPath $target | ConvertFrom-Json
            if ($geoJson.type -notin @('Feature', 'FeatureCollection')) {
                $invalidGeoJson.Add([string] $url)
            }
        } catch {
            $invalidGeoJson.Add([string] $url)
        }
    }
}

if ($missing.Count -or $invalidGeoJson.Count) {
    if ($missing.Count) { Write-Error ("Missing files:`n - " + ($missing -join "`n - ")) }
    if ($invalidGeoJson.Count) { Write-Error ("Invalid GeoJSON:`n - " + ($invalidGeoJson -join "`n - ")) }
    exit 1
}

Write-Output ("Validated manifest: {0} basemaps, {1} repository layers, {2} repository satellite assets, and {3} environmental analysis files." -f @($manifest.basemaps).Count, @($manifest.layers).Count, @($manifest.satellite_assets).Count, @($environmentalUrls).Count)
