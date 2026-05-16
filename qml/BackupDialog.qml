// qml/BackupDialog.qml
// ────────────────────
// Dialog to create encrypted backups or restore from an existing backup.
//
// Design: Clean two-tab layout with clear primary actions, proper error/
// success feedback areas, and informative guidance text.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import "components"

Popup {
    id: root
    anchors.centerIn: parent
    width: 520
    modal: true; dim: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        color: Theme.bgBase; radius: Theme.radiusLG
        border.color: Theme.bgBorder; border.width: 1
    }

    onClosed: {
        errBox.visible     = false
        successBox.visible = false
        tabBar.currentIndex = 0
    }

    // ── File Dialogs ───────────────────────────
    FileDialog {
        id: saveDlg
        title: "Save Backup As"
        fileMode: FileDialog.SaveFile
        nameFilters: ["khazna Backup (*.svbak)", "All Files (*)"]
        onAccepted: {
            errBox.visible = false; successBox.visible = false
            var path = selectedFile.toString()
            if (Qt.platform.os === "windows")
                path = path.replace(/^file:\/\/\//, "")
            else
                path = path.replace(/^file:\/\//, "")
            var ok = vault.exportBackup(path, exportPwdInput.text)
            if (ok) {
                successLabel.text = "✓  Backup saved successfully."
                successBox.visible = true
            } else {
                errLabel.text = "Backup failed — check the destination path and try again."
                errBox.visible = true
            }
        }
    }

    FileDialog {
        id: openDlg
        title: "Select Backup File"
        fileMode: FileDialog.OpenFile
        nameFilters: ["khazna Backup (*.svbak)", "All Files (*)"]
        onAccepted: {
            errBox.visible = false; successBox.visible = false
            var path = selectedFile.toString()
            if (Qt.platform.os === "windows")
                path = path.replace(/^file:\/\/\//, "")
            else
                path = path.replace(/^file:\/\//, "")
            var ok = vault.importBackup(path, restorePwdInput.text)
            if (ok) {
                successLabel.text = "✓  Restore complete! Entries have been merged into your vault."
                successBox.visible = true
            } else {
                errLabel.text = "Restore failed — see details above or check the log."
                errBox.visible = true
            }
        }
    }

    // ── Listen for backend errors ──────────────
    Connections {
        target: vault
        function onErrorOccurred(msg) {
            if (root.visible) {
                errLabel.text = msg
                errBox.visible = true
                successBox.visible = false
            }
        }
    }

    contentItem: ColumnLayout {
        anchors { fill: parent; margins: 28 }
        spacing: 20

        // ── Header ─────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 40; height: 40; radius: 10
                color: Theme.cyanBg
                border.color: Theme.cyanBorder; border.width: 1
                Text {
                    anchors.centerIn: parent; text: "📦"
                    font.pointSize: 17
                }
            }

            Column {
                spacing: 2
                Text {
                    text: "Backup & Restore"
                    color: Theme.textPrimary; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeXL; font.weight: Font.Bold
                }
                Text {
                    text: "Create or restore encrypted vault backups"
                    color: Theme.textMuted; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeXS
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                width: 32; height: 32; radius: 16
                color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                Text {
                    anchors.centerIn: parent; text: "✕"
                    color: Theme.textMuted; font.pointSize: 13
                }
                MouseArea {
                    id: closeMa; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                }
            }
        }

        // ── Tabs ───────────────────────────────────
        RowLayout {
            Layout.fillWidth: true; spacing: 4

            Repeater {
                model: ["Create Backup", "Restore Backup"]

                Rectangle {
                    Layout.fillWidth: true; height: 38; radius: Theme.radiusSM

                    property bool active: tabBar.currentIndex === index
                    color: active ? Theme.cyanBg : "transparent"
                    border.color: active ? Theme.cyanBorder : Theme.bgBorder
                    border.width: 1

                    Behavior on color        { ColorAnimation { duration: Theme.animFast } }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                    Text {
                        anchors.centerIn: parent; text: modelData
                        color: parent.active ? Theme.cyan : Theme.textSecondary
                        font.family: Theme.fontFamily; font.weight: Font.DemiBold
                        font.pointSize: Theme.fontSizeSM
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            tabBar.currentIndex = index
                            errBox.visible = false
                            successBox.visible = false
                        }
                    }
                }
            }
        }

        Item { id: tabBar; property int currentIndex: 0; visible: false }

        // ── Status / error feedback ───────────────
        Rectangle {
            id: errBox
            Layout.fillWidth: true; visible: false
            radius: Theme.radiusMD
            color: Theme.dangerBg; border.color: Theme.dangerBorder; border.width: 1
            implicitHeight: errCol.implicitHeight + 28

            ColumnLayout {
                id: errCol
                anchors {
                    left: parent.left; right: parent.right
                    verticalCenter: parent.verticalCenter
                    margins: 14
                }
                spacing: 4

                Text {
                    Layout.fillWidth: true
                    text: "⚠  Error"
                    color: Theme.danger; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM; font.weight: Font.Bold
                }
                Text {
                    id: errLabel
                    Layout.fillWidth: true
                    color: Theme.danger; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeXS; wrapMode: Text.Wrap
                    lineHeight: 1.4; opacity: 0.9
                }
            }
        }

        Rectangle {
            id: successBox
            Layout.fillWidth: true; visible: false
            radius: Theme.radiusMD
            color: Theme.successBg; border.color: Theme.successBorder; border.width: 1
            implicitHeight: successLabel.implicitHeight + 28

            Text {
                id: successLabel
                anchors {
                    left: parent.left; right: parent.right
                    verticalCenter: parent.verticalCenter; margins: 14
                }
                color: Theme.success; font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeSM; wrapMode: Text.Wrap
                font.weight: Font.DemiBold
            }
        }

        // ── Create Backup Tab ─────────────────────
        ColumnLayout {
            Layout.fillWidth: true; spacing: 16
            visible: tabBar.currentIndex === 0

            Rectangle {
                Layout.fillWidth: true; radius: Theme.radiusMD
                color: Theme.bgSurface; border.color: Theme.bgBorder; border.width: 1
                implicitHeight: createInfo.implicitHeight + 32

                ColumnLayout {
                    id: createInfo
                    anchors {
                        left: parent.left; right: parent.right
                        verticalCenter: parent.verticalCenter; margins: 16
                    }
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        text: "🔒  Encrypted Backup"
                        color: Theme.textPrimary; font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeSM; font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Creates a fully encrypted, self-contained backup. " +
                              "The backup will be encrypted with the password you provide below. " +
                              "You will need this exact password to restore it later."
                        color: Theme.textSecondary; font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeXS; wrapMode: Text.Wrap
                        lineHeight: 1.5
                    }
                }
            }
            
            SvField {
                id: exportPwdInput
                Layout.fillWidth: true
                label: "Backup Password"
                placeholder: "Enter a strong password (optional, uses current if blank)"
                echoMode: TextInput.Password
                showToggle: true
            }

            RowLayout {
                Layout.fillWidth: true; Layout.topMargin: 4
                Item { Layout.fillWidth: true }
                SvButton {
                    text: "Choose Location & Save"
                    iconLabel: "💾"
                    variant: "primary"
                    onClicked: saveDlg.open()
                }
            }
        }

        // ── Restore Backup Tab ────────────────────
        ColumnLayout {
            Layout.fillWidth: true; spacing: 16
            visible: tabBar.currentIndex === 1

            Rectangle {
                Layout.fillWidth: true; radius: Theme.radiusMD
                color: Theme.warningBg; border.color: Theme.warningBorder; border.width: 1
                implicitHeight: restoreInfo.implicitHeight + 32

                ColumnLayout {
                    id: restoreInfo
                    anchors {
                        left: parent.left; right: parent.right
                        verticalCenter: parent.verticalCenter; margins: 16
                    }
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        text: "⚠  Important"
                        color: Theme.warning; font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeSM; font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Entries from the backup will be merged into your current vault. " +
                              "Duplicate entries (same ID) are skipped.\n\n" +
                              "If you are restoring a self-contained backup or a backup from an old vault, " +
                              "you MUST enter the password that was used to create it."
                        color: Theme.textSecondary; font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeXS; wrapMode: Text.Wrap
                        lineHeight: 1.5
                    }
                }
            }

            SvField {
                id: restorePwdInput
                Layout.fillWidth: true
                label: "Original Master Password"
                placeholder: "Password used when backup was created (required for V4)"
                echoMode: TextInput.Password
                showToggle: true
            }

            RowLayout {
                Layout.fillWidth: true; Layout.topMargin: 4
                Item { Layout.fillWidth: true }
                SvButton {
                    text: "Select Backup File"
                    iconLabel: "📂"
                    variant: "default"
                    onClicked: openDlg.open()
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
