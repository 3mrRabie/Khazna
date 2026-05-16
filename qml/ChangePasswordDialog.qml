// qml/ChangePasswordDialog.qml
// ────────────────────────────
// Modal dialog to change the master password.
//
// FIX: Removed onChangePasswordFinished Connections handler — no such signal
//      exists on VaultBridge.  changeMasterPassword() is a synchronous slot
//      that returns bool and emits statusMessage (success) or errorOccurred
//      (failure).  We call it directly and check the return value.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Popup {
    id: root
    anchors.centerIn: parent
    width: 440
    modal: true; dim: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        color: Theme.bgBase; radius: Theme.radiusLG
        border.color: Theme.bgBorder; border.width: 1
    }

    onClosed: {
        oldPwField.text = ""
        newPwField.text = ""
        confirmField.text = ""
        errBox.visible     = false
        successBox.visible = false
        strengthBar.clear()
    }

    Connections {
        target: vault
        function onStrengthResult(score, level, colour, tips) {
            if (root.visible) strengthBar.setStrength(score, level, colour, tips)
        }
        // FIX: No onChangePasswordFinished signal exists. We handle result via the
        //      return value of vault.changeMasterPassword() called in _submit().
        // errorOccurred is emitted by the bridge on failure for status bar feedback;
        // we show our own inline error via the returned bool.
    }

    contentItem: ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 20

        // ── Header ─────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                width: 36; height: 36; radius: 8; color: Theme.cyanBg
                Text { anchors.centerIn: parent; text: "🔑"; font.pointSize: 16 }
            }
            Item { width: 8 }
            Text {
                text: "Change Password"
                color: Theme.textPrimary; font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeH2; font.weight: Font.Bold
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: 32; height: 32; radius: 16
                color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                Text { anchors.centerIn: parent; text: "✕"; color: Theme.textMuted; font.pointSize: 14 }
                MouseArea { id: closeMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
            }
        }

        // ── Form ──────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true; spacing: 16

            SvField {
                id: oldPwField; Layout.fillWidth: true
                label: "Current Password"; placeholder: "Enter current master password"
                echoMode: TextInput.Password; showToggle: true
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.bgBorder; opacity: 0.5 }

            SvField {
                id: newPwField; Layout.fillWidth: true
                label: "New Password"; placeholder: "Enter new master password"
                echoMode: TextInput.Password; showToggle: true
                onTextEdited: (t) => vault.checkStrength(t)
            }

            StrengthBar { id: strengthBar; Layout.fillWidth: true }

            SvField {
                id: confirmField; Layout.fillWidth: true
                label: "Confirm New Password"; placeholder: "Confirm new master password"
                echoMode: TextInput.Password; showToggle: true
            }

            // Error
            Rectangle {
                id: errBox; Layout.fillWidth: true; visible: false; radius: Theme.radiusMD
                height: errLabel.implicitHeight + 24; color: Theme.dangerBg; border.color: Theme.dangerBorder
                Text { id: errLabel; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                    color: Theme.danger; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; wrapMode: Text.Wrap }
            }

            // Success
            Rectangle {
                id: successBox; Layout.fillWidth: true; visible: false; radius: Theme.radiusMD
                height: successLabel.implicitHeight + 24; color: Theme.successBg; border.color: Theme.successBorder
                Text { id: successLabel; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                    text: "Master password changed. Your vault has been re-encrypted."
                    color: Theme.success; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; wrapMode: Text.Wrap }
            }

            RowLayout {
                Layout.fillWidth: true; Layout.topMargin: 8
                Item { Layout.fillWidth: true }
                SvButton {
                    text: "Update Password"
                    variant: "primary"
                    onClicked: _submit()
                }
            }
        }
    }

    function _submit() {
        errBox.visible     = false
        successBox.visible = false

        if (newPwField.text !== confirmField.text) {
            errLabel.text  = "New passwords do not match."
            errBox.visible = true
            return
        }
        if (newPwField.text.length < 8) {
            errLabel.text  = "New password must be at least 8 characters."
            errBox.visible = true
            return
        }

        // changeMasterPassword returns bool; errors are also emitted via errorOccurred
        var ok = vault.changeMasterPassword(oldPwField.text, newPwField.text)
        if (ok) {
            successBox.visible = true
            oldPwField.text    = ""
            newPwField.text    = ""
            confirmField.text  = ""
            strengthBar.clear()
        } else {
            // Bridge emits errorOccurred with the message; mirror it inline too.
            errLabel.text  = "Password change failed. Check your current password and try again."
            errBox.visible = true
        }
    }
}
