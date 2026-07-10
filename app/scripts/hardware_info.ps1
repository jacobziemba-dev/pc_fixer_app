$ErrorActionPreference = 'SilentlyContinue'

$cpu = Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$gpu = Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion
$system = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, SystemFamily, TotalPhysicalMemory
$board = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product
$bios = Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture, InstallDate
$diskDrives = Get-CimInstance Win32_DiskDrive | Select-Object Model, Size, InterfaceType

$physicalDisks = @()
try {
    $physicalDisks = Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size, HealthStatus
} catch {}

$memoryModules = Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, Manufacturer, DeviceLocator

$result = [PSCustomObject]@{
    cpu           = $cpu
    gpu           = $gpu
    system        = $system
    board         = $board
    bios          = $bios
    os            = $os
    diskDrives    = $diskDrives
    physicalDisks = $physicalDisks
    memoryModules = $memoryModules
}

$result | ConvertTo-Json -Depth 6
