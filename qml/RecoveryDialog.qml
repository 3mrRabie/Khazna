// qml/RecoveryDialog.qml
// ──────────────────────
// Generate or use emergency recovery keys.
//
// FIXES vs original
// ─────────────────
// • On successful recovery the backend NOW locks the vault so the user
//   must re-authenticate.  The dialog detects this and closes itself;
//   Main.qml transitions to LoginScreen automatically via lockStateChanged.
// • The "Recover Vault" button is disabled while the operation is in
//   flight (prevents double-submit).
// • Input field accepts codes with OR without hyphens/spaces — the backend
//   normalises before validation.
// • Format hint shown below the input field at all times.
// • Multi-line success message rendered properly.
// • "Copy Keys" copies the full block of all 8 codes (newline-separated),
//   which is what the user needs to save.
// • Error message is shown in the generate flow too (e.g. vault locked).
// • onClosed clears sensitive state (key text, password field).

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Popup {
    id: root

    // ── Public API ────────────────────────────
    // Set showRecoveryFlow = true  → "enter a code to recover the vault"
    // Set showRecoveryFlow = false → "generate & display new recovery codes"
    property bool showRecoveryFlow: false

    // ── Internal state ────────────────────────
    property bool _busy: false

    anchors.centerIn: parent
    width:  540
    modal:  true
    dim:    true
    // Do not allow closing while busy.
    closePolicy: _busy ? Popup.NoAutoClose
                       : Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        color:  Theme.bgBase
        radius: Theme.radiusLG
        border.color: Theme.bgBorder
        border.width: 1
        Rectangle {
            anchors.fill:    parent
            anchors.margins: -1
            radius:          parent.radius + 1
            color:           "transparent"
            border.color:    Theme.accentGlow
            border.width:    1
            z: -1
        }
    }

    // ── Lifecycle ─────────────────────────────
    onOpened: {
        root._busy         = false
        errBox.visible     = false
        successBox.visible = false

        if (!root.showRecoveryFlow) {
            keysText.text = "Generating…"
            // generateRecoveryKeys() is synchronous from QML's perspective;
            // the codes arrive via onRecoveryKeysGenerated.
            vault.generateRecoveryKeys()
        } else {
            keyInput.text  = ""
            newPwInput.text = ""
        }
    }

    onClosed: {
        // Clear sensitive fields on close.
        keysText.text   = ""
        keyInput.text   = ""
        newPwInput.text = ""
        errBox.visible     = false
        successBox.visible = false
        root._busy = false
    }

    // ── Bridge connections ────────────────────
    Connections {
        target: vault

        // ── Generate flow: codes have been produced and stored ──────────
        function onRecoveryKeysGenerated(keys) {
            if (!root.visible || root.showRecoveryFlow) return
            // Use keys.length directly as marshalled QVariantLists might not satisfy Array.isArray()
            if (keys && keys.length > 0) {
                keysText.text = keys.join("\n")
            } else {
                keysText.text = "(error — no codes returned)"
                genErrLabel.text = "Code generation failed. Make sure the vault is unlocked."
                genErrBox.visible = true
                _log.error("onRecoveryKeysGenerated: received empty or invalid keys list")
            }
        }

        // ── Recovery flow: result from recoverWithCode ──────────────────
        function onRecoveryComplete(success, message) {
            if (!root.visible) return
            root._busy = false

            if (success) {
                // Show the success banner, then close after a short pause.
                // Main.qml will transition to LoginScreen automatically
                // because vault.isLocked becomes true and lockStateChanged fires.
                successLabel.text  = message
                successBox.visible = true
                errBox.visible     = false
                keyInput.text      = ""
                newPwInput.text    = ""
                closeTimer.start()
            } else {
                errLabel.text  = message
                errBox.visible = true
                successBox.visible = false
            }
        }
    }

    // Auto-close after success so the login screen appears cleanly.
    Timer {
        id: closeTimer
        interval: 2800
        onTriggered: root.close()
    }

    // ── Content ───────────────────────────────
    contentItem: ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 20

        // ── Header ─────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 36; height: 36; radius: 8
                color: root.showRecoveryFlow ? Theme.dangerBg : Theme.cyanBg
                Text {
                    anchors.centerIn: parent
                    text: root.showRecoveryFlow ? "🔓" : "🛟"
                    font.pointSize: 16
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: root.showRecoveryFlow ? "Recover Vault" : "Recovery Keys"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeH2
                    font.weight: Font.Bold
                }
                Text {
                    text: root.showRecoveryFlow
                        ? "Enter one of your 8 recovery codes to regain access."
                        : "8 one-time emergency codes for this vault."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                }
            }

            Rectangle {
                width: 32; height: 32; radius: 16
                color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                visible: !root._busy
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: Theme.textMuted
                    font.pointSize: 14
                }
                MouseArea {
                    id: closeMa
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                }
            }
        }

        // ════════════════════════════════════════
        // GENERATE FLOW
        // ════════════════════════════════════════
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: !root.showRecoveryFlow

            // Info banner
            Rectangle {
                Layout.fillWidth: true
                height: infoCol.implicitHeight + 24
                radius: Theme.radiusMD
                color: Theme.bgSurface2
                border.color: Theme.bgBorder

                ColumnLayout {
                    id: infoCol
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    spacing: 6

                    RowLayout {
                        spacing: 8
                        Text { text: "ℹ"; color: Theme.cyan; font.pointSize: Theme.fontSizeMD }
                        Text {
                            Layout.fillWidth: true
                            text: "These 8 codes each independently unlock your vault."
                            color: Theme.textSecondary
                            font.family: Theme.fontFamily
                            font.pointSize: Theme.fontSizeSM
                            wrapMode: Text.Wrap
                        }
                    }
                    RowLayout {
                        spacing: 8
                        Text { text: "⚠"; color: Theme.warning; font.pointSize: Theme.fontSizeSM }
                        Text {
                            Layout.fillWidth: true
                            text: "These codes are shown ONCE and cannot be recovered. Save them offline."
                            color: Theme.warning
                            font.family: Theme.fontFamily
                            font.pointSize: Theme.fontSizeSM
                            wrapMode: Text.Wrap
                        }
                    }
                    RowLayout {
                        spacing: 8
                        Text { text: "🔄"; color: Theme.textMuted; font.pointSize: Theme.fontSizeSM }
                        Text {
                            Layout.fillWidth: true
                            text: "Using any one code to recover the vault invalidates all 8."
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pointSize: Theme.fontSizeSM
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }

            // Keys display box
            Rectangle {
                Layout.fillWidth: true
                height: 210
                radius: Theme.radiusMD
                color: Theme.bgBase
                border.color: Theme.dangerBorder
                border.width: 1

                // Scrollable in case text overflows (unlikely but defensive)
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 16
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Text {
                        id: keysText
                        width: parent.width
                        color: Theme.danger
                        font.family: "Consolas, Courier New, monospace"
                        font.pointSize: Theme.fontSizeMD
                        font.weight: Font.Bold
                        horizontalAlignment: Text.AlignHCenter
                        lineHeight: 1.9
                        wrapMode: Text.WrapAnywhere
                        text: "Generating…"
                    }
                }
            }

            // Format label
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Format: XXXXX-XXXXX-XXXXX-XXXXX"
                color: Theme.textMuted
                font.family: "Consolas, Courier New, monospace"
                font.pointSize: Theme.fontSizeXS
            }

            // Error (generation failure)
            Rectangle {
                id: genErrBox
                Layout.fillWidth: true
                visible: false
                height: genErrLabel.implicitHeight + 20
                radius: Theme.radiusMD
                color: Theme.dangerBg
                border.color: Theme.dangerBorder
                Text {
                    id: genErrLabel
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                    color: Theme.danger
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    wrapMode: Text.Wrap
                }
            }

            // Action row
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Copy all codes
                SvButton {
                    text: "📋  Copy All Codes"
                    Layout.fillWidth: true
                    onClicked: {
                        if (keysText.text && keysText.text !== "Generating…")
                            vault.copyToClipboard(keysText.text)
                    }
                }

                // Regenerate (replaces existing codes)
                SvButton {
                    text: "🔄  Regenerate"
                    onClicked: {
                        keysText.text = "Generating…"
                        genErrBox.visible = false
                        vault.generateRecoveryKeys()
                    }
                }
            }
        }

        // ════════════════════════════════════════
        // RECOVER FLOW
        // ════════════════════════════════════════
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: root.showRecoveryFlow

            // How-to hint
            Rectangle {
                Layout.fillWidth: true
                height: howToText.implicitHeight + 20
                radius: Theme.radiusMD
                color: Theme.bgSurface2
                border.color: Theme.bgBorder

                Text {
                    id: howToText
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    text: "Enter any one of your 8 recovery codes and choose a new master password.\n" +
                          "Hyphens and spaces are optional — the code is accepted in any format."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    wrapMode: Text.Wrap
                    lineHeight: 1.4
                }
            }

            // Recovery code input
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Recovery Code"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    font.weight: Font.Medium
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: Theme.radiusMD
                    color: Theme.bgSurface
                    border.color: keyInput.activeFocus ? Theme.cyan : Theme.bgBorder
                    border.width: keyInput.activeFocus ? 2 : 1
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                    TextField {
                        id: keyInput
                        anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
                        background: Item {}
                        color: Theme.textPrimary
                        font.family: "Consolas, Courier New, monospace"
                        font.pointSize: Theme.fontSizeMD
                        placeholderText: "XXXXX-XXXXX-XXXXX-XXXXX"
                        placeholderTextColor: Theme.textMuted
                        selectByMouse: true
                        enabled: !root._busy
                        onTextChanged: {
                            // Clear stale error when user types
                            errBox.visible = false
                        }
                    }
                }

                Text {
                    text: "20 alphanumeric characters. Hyphens and spaces are ignored."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeXS
                }
            }

            // New master password input
            SvField {
                id: newPwInput
                Layout.fillWidth: true
                label: "New Master Password"
                placeholder: "Minimum 8 characters"
                echoMode: TextInput.Password
                showToggle: true
                readOnly: root._busy
                onTextEdited: (t) => {
                    errBox.visible = false
                }
            }

            // ── Status boxes ───────────────────────────
            Rectangle {
                id: errBox
                Layout.fillWidth: true
                visible: false
                height: errLabel.implicitHeight + 24
                radius: Theme.radiusMD
                color: Theme.dangerBg
                border.color: Theme.dangerBorder

                Text {
                    id: errLabel
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    color: Theme.danger
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    wrapMode: Text.Wrap
                    lineHeight: 1.4
                }
            }

            Rectangle {
                id: successBox
                Layout.fillWidth: true
                visible: false
                height: successLabel.implicitHeight + 24
                radius: Theme.radiusMD
                color: Theme.successBg
                border.color: Theme.successBorder

                Text {
                    id: successLabel
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    color: Theme.success
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    wrapMode: Text.Wrap
                    lineHeight: 1.5
                }
            }

            // ── Recover button ─────────────────────────
            SvButton {
                Layout.fillWidth: true
                text: root._busy ? "Recovering…" : "Recover Vault"
                variant: "danger"
                enabled: !root._busy
                onClicked: _submitRecovery()
            }
        }
    }

    // ── Logic ─────────────────────────────────

    function _submitRecovery() {
        errBox.visible     = false
        successBox.visible = false

        var code = keyInput.text.trim()
        var pw   = newPwInput.text

        if (code === "") {
            errLabel.text  = "Please enter your recovery code."
            errBox.visible = true
            return
        }
        if (pw.length < 8) {
            errLabel.text  = "New master password must be at least 8 characters."
            errBox.visible = true
            return
        }

        root._busy = true
        // recoverWithCode is synchronous — result arrives via onRecoveryComplete.
        vault.recoverWithCode(code, pw)
    }
}
