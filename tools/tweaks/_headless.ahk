; _headless.ahk — headless driver for acediez's MMX6 Tweaks patcher engine.
;
; Runs the REAL patcher pipeline (createlist / exception_a / exception_b /
; filter / patchapply) with no GUI interaction, so the recompiler's variant
; tooling (tools/tweaks_resolver.py) can produce a patched BIN that is
; byte-identical to the shipped standalone patches and the GUI's own output.
;
; VALIDATED byte-identical (MD5) against all three shipped v2.6 standalone
; patches: [Tweaks] (b01), [Tweaks+Localization] (s02), and
; [Tweaks+Localization+Custom Art] (s02 + mugshot assembly + art file inserts).
;
; This file is TRACKED. At apply time the resolver copies it into the user's
; in-place extracted patcher "_src" directory (so the #Include lines below
; resolve relatively) and runs it via AutoHotkey v1.1. Nothing of acediez's
; data is redistributed — his engine + payloads are read in place from the
; archive the user supplied.
;
; Usage:
;   AutoHotkeyU64.exe _headless.ahk <profile> <inputBin> <resultFile> <toolsRoot> [nowrite]
;     <profile>    default | tweaks | tweaks_l | tweaks_l_c
;                  or an absolute path to a .x6tweaksprofile file
;     <inputBin>   vanilla "Mega Man X6 (USA) (v1.1).bin" (MD5 237B6FEDDD...)
;     <resultFile> file to receive the produced OutputPath (one line) on success
;     <toolsRoot>  dir holding tools\ and data\ (the patcher's run-extracted dir:
;                  xdelta3, error_recalc, xdelta3\{b01,s02}, asset dirs)
;     [nowrite]    optional literal "nowrite" -> NoWriteMode (build mod list, no I/O)

#SingleInstance Force
#NoTrayIcon
#Warn, All, Off
SetBatchLines, -1
DetectHiddenWindows, On

FormatTime, Date,, yyyyMMdd

; ---- args ----------------------------------------------------------------
ProfileArg   := A_Args[1]
InputArg     := A_Args[2]
ResultArg    := A_Args[3]
ToolsRootArg := A_Args[4]
DryRunArg    := A_Args[5]

if (ProfileArg = "" or InputArg = "" or ResultArg = "" or ToolsRootArg = "") {
    FileAppend, ERROR: usage: _headless.ahk <profile> <inputBin> <resultFile> <toolsRoot> [nowrite]`n, *
    ExitApp, 2
}
if !FileExist(InputArg) {
    FileAppend, ERROR: input not found: %InputArg%`n, *
    ExitApp, 2
}

; ---- BasicData (mirror of x6tweaks.ahk, paths repointed to toolsRoot) -----
Version = v2.6.1
ProjectPage = http://www.romhacking.net/utilities/1414/
ReferenceHash = 237B6FEDDD1A88E86AB1CDDC8822F03F
Title = Mega Man X6 Tweaks Patcher (%Version%)
OutputSuffix_Name = Tweaks %Version% Build %Date%
OutputSuffix_Brackets = 1
OutputSuffix_VersionCoding = _
ProgressStartParam = b1 w190 h30 zx6
ProgressPatchParam = b1 zh0 fs10 w190

TabDefault = 1
OutputDec = 1
PatchList_BaseHacks = 1
ErrorRecalc = 1
HelpButtonStart = 0
NativeWrite = 1

ToolsDir = %ToolsRootArg%\tools
ErrorRecalcPath = %ToolsDir%\error_recalc\error_recalc.exe
xdelta3Path = %ToolsDir%\xdelta3\xdelta3-3.0.11-i686.exe
ExtDataDir = %ToolsRootArg%\data
PatchDir = %ExtDataDir%\xdelta3
SamplesDir = %ExtDataDir%\sample

PatchMsg_Start = `nProcessing selected options...`n
PatchMsg_FileFilter = `nReading external files...`n
PatchMsg_ECCSplitFilter = `nCalculating data offsets...`n
PatchMsg_xdelta3 = `nApplying base patch (xdelta3)...`n
PatchMsg_xdelta3_WaitAccess = `nWaiting for file access...`n
PatchMsg_BatchHex_Ini = `nBuilding list of modifications...`n
PatchMsg_BatchHex = `nWriting on BIN file...`n
PatchMsg_ErrorRecalc = `nEDC/ECC Recalculator...`n
PatchMsg_xdeltaFail = xdelta3 patching failed.
PatchMsg_Success1 = BIN successfuly patched!
PatchMsg_Success2 =
PatchMsg_Success3 =

; Headless flags
DebugMode = 0
NoWriteMode = 0
DumpMode := 0
if (DryRunArg = "nowrite")
    NoWriteMode = 1
if (DryRunArg = "dump") {
    ; Oracle mode for the Python port: build the mod list but write no BIN, then
    ; dump the engine's final WriteList (data,offset) + file inserts + base patch.
    NoWriteMode = 1
    DumpMode := 1
}
SaveMode := (DryRunArg = "save")   ; load the profile, ProfileSave it, exit (no patch)
DebugBatchPatch = 1      ; skip the success MsgBox at PatchEnd
PatchShowWin = 0         ; Run xdelta3/error_recalc hidden
Versioning = 1           ; force OutputFileNext auto-numbering (never the overwrite prompt)

if !FileExist(xdelta3Path) {
    FileAppend, ERROR: xdelta3 not found: %xdelta3Path%`n, *
    ExitApp, 2
}

; ---- optional step trace -------------------------------------------------
TraceFile := A_ScriptDir "\_headless_trace.log"
FileDelete, %TraceFile%

; ---- Engine init (mirror of x6tweaks.ahk auto-exec, minus FileInstall) ----
TR("start")
GoSub ProfileDefault
GoSub DAT_Init
GoSub DAT
GoSub HelpDat
GoSub DmgTableInit
GoSub DmgTableDivide
GoSub GUI
Gui, Main:Hide
Gui, Main:+Disabled
TR("engine ready")

; ---- Input ---------------------------------------------------------------
InputPath := InputArg
SplitPath, InputPath, InputFileName, InputDir, InputExt, InputFileNameNoExt

; ---- Select profile ------------------------------------------------------
ProfileString :=
if (ProfileArg = "default")
    ProfileString := ProfileDefault_Default
else if (ProfileArg = "tweaks")
    ProfileString := ProfileDefault_Tweaks
else if (ProfileArg = "tweaks_l")
    ProfileString := ProfileDefault_Tweaks_L
else if (ProfileArg = "tweaks_l_c")
    ProfileString := ProfileDefault_Tweaks_L_C
else if FileExist(ProfileArg)
    FileRead, ProfileString, %ProfileArg%

if (ProfileString = "") {
    FileAppend, ERROR: unknown/empty profile: %ProfileArg%`n, *
    ExitApp, 2
}
ProfileLoad(ProfileString)
TR("profile loaded: " ProfileArg)

; ---- Save mode: dump the fully-resolved profile (VarList=values) and exit ----
if (SaveMode) {
    ProfileSave(ResultArg)
    FileAppend, SAVE OK: %ResultArg%`n, *
    ExitApp, 0
}

; ---- Apply ---------------------------------------------------------------
GoSub Patch
TR("patch done: " OutputPath)

; ---- Report --------------------------------------------------------------
if (DumpMode = 1) {
    ; Emit the ground-truth apply plan for the Python port to match:
    ;   PATCHFILE=<b01|s02>   (base xdelta3 selected by ScriptPatch)
    ;   [WRITELIST]  data,offset  (hex writes; offset per OutputDec)
    ;   [FILES]      varname,filepath  (asset inserts, ECC-split at write time)
    FileDelete, %ResultArg%
    FileAppend, PATCHFILE=%PatchFile%`n, %ResultArg%
    FileAppend, [WRITELIST]`n, %ResultArg%
    FileAppend, %WriteList%, %ResultArg%
    FileAppend, `n[FILES]`n, %ResultArg%
    FileAppend, %PatchList_Files%, %ResultArg%
    FileAppend, DUMP OK: %ResultArg%`n, *
    ExitApp, 0
}
if (NoWriteMode = 1) {
    FileDelete, %ResultArg%
    FileAppend, %OutputPath%, %ResultArg%
    FileAppend, OK(nowrite): %OutputPath%`n, *
    ExitApp, 0
}
if !FileExist(OutputPath) {
    FileAppend, ERROR: output not produced (OutputPath=%OutputPath%)`n, *
    ExitApp, 1
}
FileDelete, %ResultArg%
FileAppend, %OutputPath%, %ResultArg%
FileAppend, OK: %OutputPath%`n, *
ExitApp, 0

TR(msg) {
    global TraceFile
    FileAppend, % msg "`n", %TraceFile%
}

; Stubs for labels defined in x6tweaks.ahk (the main file we intentionally omit).
Clock:
Return

; ---- Engine source (read in place from the user's patcher archive) -------
#Include %A_ScriptDir%
#Include _lib\_HexLib.ahk
#Include _gui\debug.ahk
#Include _gui\gui.ahk
#Include _gui\guicontrol.ahk
#Include _gui\dmgtable.ahk
#Include _gui\profile.ahk
#Include _gui\sample.ahk
#Include _gui\help.ahk
#Include _patch\createlist.ahk
#Include _patch\exception_a.ahk
#Include _patch\exception_b.ahk
#Include _patch\patch.ahk
#Include _patch\filter.ahk
#Include _patch\patchapply.ahk
#Include data\_dat_init.ahk
#Include data\_dat.ahk
#Include profiles\_include.ahk
