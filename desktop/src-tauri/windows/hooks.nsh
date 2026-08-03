; Enable WSL2 during installation, while we are already elevated.
;
; Windows cannot run bioinformatics tools natively -- bioconda publishes no
; win-64 packages -- so local execution needs a Linux userland. Enabling the
; Windows features for that is a machine-wide operation requiring administrator
; rights, which the installer has and the application deliberately does not.
;
; Everything after this point (importing the distribution, installing the
; engine) needs no elevation at all, so the app itself runs unprivileged.
;
; This is best-effort by design. A failure here is not an installation failure:
; the app detects the situation at first run, explains it, and offers cloud
; execution instead.

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Checking for Windows Subsystem for Linux..."

  ; A non-zero exit means WSL is absent or its features are disabled. wsl.exe
  ; exists as a stub even then, so presence of the binary proves nothing.
  nsExec::ExecToStack '"$SYSDIR\wsl.exe" --status'
  Pop $0
  ${If} $0 == 0
    DetailPrint "WSL is already enabled."
    Goto wsl_done
  ${EndIf}

  DetailPrint "Enabling WSL2 (this may take a few minutes)..."

  ; Preferred path on Windows 11: enables both features and installs the
  ; kernel. --no-distribution keeps us from installing an Ubuntu the user did
  ; not ask for; BioNodulo imports its own private distribution later.
  nsExec::ExecToLog '"$SYSDIR\wsl.exe" --install --no-distribution'
  Pop $0
  ${If} $0 == 0
    StrCpy $1 "1"
    Goto wsl_enabled
  ${EndIf}

  ; Fallback for builds whose wsl.exe predates --no-distribution: enable the
  ; two optional components directly. This is exactly what `wsl --install`
  ; does, and it needs neither the Store nor the network.
  DetailPrint "Falling back to enabling Windows features directly..."
  nsExec::ExecToLog '"$SYSDIR\dism.exe" /online /enable-feature \
    /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart'
  Pop $0
  nsExec::ExecToLog '"$SYSDIR\dism.exe" /online /enable-feature \
    /featurename:VirtualMachinePlatform /all /norestart'
  Pop $2

  ; 3010 is "success, reboot required" and is the normal outcome here.
  ${If} $0 == 0
  ${OrIf} $0 == 3010
    ${If} $2 == 0
    ${OrIf} $2 == 3010
      StrCpy $1 "1"
      Goto wsl_enabled
    ${EndIf}
  ${EndIf}

  DetailPrint "Could not enable WSL2 automatically."
  MessageBox MB_OK|MB_ICONINFORMATION \
    "BioNodulo could not enable WSL2 on this PC, so workflows cannot run locally yet.$\n$\n\
     This usually means hardware virtualization is turned off in the BIOS or UEFI \
     settings, or that company policy restricts it.$\n$\n\
     You can still run workflows on the cloud, which needs no setup. To retry local \
     setup later, use Settings inside the app."
  Goto wsl_done

wsl_enabled:
  ; The features are enabled but the subsystem is not usable until Windows
  ; restarts. Record it so first run can say so plainly instead of failing with
  ; a confusing error.
  WriteRegStr HKLM "Software\BioNodulo" "WslRebootPending" "1"
  DetailPrint "WSL2 enabled. A restart is required before workflows can run locally."
  MessageBox MB_OK|MB_ICONINFORMATION \
    "BioNodulo enabled WSL2 so workflows can run on this PC.$\n$\n\
     Please restart Windows to finish. Until then, workflows will run on the cloud."

wsl_done:
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; The private distribution lives outside the install directory, so removing
  ; the app would otherwise strand several GB of disk. WSL itself is left
  ; enabled: it is a Windows feature the user may rely on elsewhere.
  nsExec::ExecToLog '"$SYSDIR\wsl.exe" --unregister BioNodulo'
  Pop $0
  DeleteRegValue HKLM "Software\BioNodulo" "WslRebootPending"
!macroend
