// qml/DashboardScreen.qml
// ────────────────────────
// Primary authenticated screen.  Shows Sidebar + EntryTable.
// Hosts all dialogs; entry CRUD flows through VaultBridge slots.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import "components"

Item {
    id: root

    // ── Dialogs (lazy-created) ────────────────
    property var _entryDlg:      null
    property var _genDlg:        null
    property var _auditDlg:      null
    property var _changePwDlg:   null
    property var _backupDlg:     null
    property var _healthDlg:     null
    property var _recoveryDlg:   null

    // ── SEC-05 FIX: Cross-platform file URL to path conversion ──────────
    function urlToPath(fileUrl) {
        var s = fileUrl.toString()
        if (Qt.platform.os === "windows") {
            if (s.indexOf("file:///") === 0)
                return s.slice(8)
        } else {
            if (s.indexOf("file://") === 0)
                return s.slice(7)
        }
        return s
    }

    // ── Keyboard shortcuts (UX-03) ────────────
    Shortcut { sequence: "Ctrl+N"; onActivated: openEntry(null) }
    Shortcut { sequence: "Ctrl+F"; onActivated: searchField.forceActiveFocus() }
    Shortcut { sequence: "Ctrl+L"; onActivated: vault.lock() }
    Shortcut {
        sequence: "Delete"
        enabled:  entryTable.selectedId >= 0
        onActivated: deleteSelected()
    }
    Shortcut {
        sequence: "Return"
        enabled:  entryTable.selectedId >= 0
        onActivated: editSelected()
    }

    // ── Main layout ───────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Toolbar row ───────────────────────
        Rectangle {
            Layout.fillWidth: true
            height:  52
            color:   Theme.bgSurface

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left:   parent.left
                anchors.right:  parent.right
                height: 1; color: Theme.bgBorder
            }

            RowLayout {
                anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
                spacing: 4

                // Primary actions
                ToolBtn { label: "➕";  tip: "Add new entry (Ctrl+N)";    fullLabel: "Add";      onClicked: openEntry(null) }
                ToolBtn { label: "✏️";  tip: "Edit selected (Enter)";     fullLabel: "Edit";     onClicked: editSelected() }
                ToolBtn { label: "🗑";  tip: "Delete selected (Del)";     fullLabel: "";         isDanger: true; onClicked: deleteSelected() }

                ToolSep {}

                ToolBtn { label: "📋";  tip: "Copy password (30 s)";      fullLabel: "Copy Pw";  onClicked: copyPw() }
                ToolBtn { label: "👁";  tip: "Reveal password (5 s)";     fullLabel: "Reveal";   onClicked: revealPw() }

                ToolSep {}

                ToolBtn { label: "⚡";  tip: "Password generator";        fullLabel: "Generate"; onClicked: openGen() }
                ToolBtn { label: "📥";  tip: "Import CSV";                fullLabel: "Import";   onClicked: importCsv() }
                ToolBtn { label: "📦";  tip: "Backup & Restore";          fullLabel: "Backup";   onClicked: openBackup() }

                ToolSep {}

                ToolBtn { label: "🔒";  tip: "Lock vault (Ctrl+L)";       fullLabel: "Lock";     onClicked: vault.lock() }

                Item { Layout.fillWidth: true }

                // Clipboard countdown badge
                Rectangle {
                    visible:       vault.clipboardCountdown > 0
                    width:         clipRow.implicitWidth + 18
                    height:        30
                    radius:        15
                    color:         Theme.cyanBg
                    border.color:  Theme.cyanBorder
                    border.width:  1

                    RowLayout {
                        id: clipRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text:  "📋"
                            font.pointSize: Theme.fontSizeXS
                        }
                        Text {
                            text:  vault.clipboardCountdown + "s"
                            color: Theme.accent
                            font.family:    Theme.fontFamily
                            font.pointSize: Theme.fontSizeSM
                            font.weight:    Font.DemiBold
                        }
                    }
                    MouseArea { id: clipMa; anchors.fill: parent; hoverEnabled: true }
                    ToolTip {
                        visible: clipMa.containsMouse
                        text:    "Clipboard will be wiped in " + vault.clipboardCountdown + " seconds"
                        delay:   400
                    }
                }

                // Search field — Raycast-style command bar
                Rectangle {
                    width:   300
                    height:  36
                    radius:  Theme.radiusMD
                    color:   Theme.bgSurface2
                    border.color: searchField.activeFocus ? Theme.accent : Theme.bgBorder
                    border.width: searchField.activeFocus ? 2 : 1
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                    RowLayout {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
                        spacing: 6
                        Text {
                            text: "🔍"
                            font.pointSize: Theme.fontSizeSM
                            color: Theme.textMuted
                        }
                        TextField {
                            id: searchField
                            Layout.fillWidth: true
                            background:     Item {}
                            color:          Theme.textPrimary
                            font.family:    Theme.fontFamily
                            font.pointSize: Theme.fontSizeSM
                            placeholderText: "Search vaults…"
                            placeholderTextColor: Theme.textMuted
                            leftPadding:  0; rightPadding: 0
                            selectByMouse: true
                            Accessible.name: "Search entries"
                            onTextChanged: {
                                vault.setSearchQuery(text)
                                entryTable._hasSearchText = (text !== "")
                            }
                        }
                        // Keyboard shortcut badge
                        Rectangle {
                            visible: searchField.text === "" && !searchField.activeFocus
                            width: kbdText.implicitWidth + 12; height: 22; radius: 4
                            color: Theme.bgSurface3
                            border.color: Theme.bgBorder
                            Text {
                                id: kbdText
                                anchors.centerIn: parent
                                text: "Ctrl+F"
                                color: Theme.textMuted
                                font.family: Theme.fontFamily
                                font.pointSize: 9
                                font.weight: Font.Medium
                            }
                        }
                        Text {
                            visible:        searchField.text !== ""
                            text:           "✕"
                            color:          Theme.textMuted
                            font.pointSize: Theme.fontSizeSM
                            MouseArea {
                                anchors.fill: parent
                                cursorShape:  Qt.PointingHandCursor
                                onClicked:    searchField.text = ""
                            }
                        }
                    }
                }
            }
        }

        // ── Body: sidebar + table ─────────────
        RowLayout {
            Layout.fillWidth:  true
            Layout.fillHeight: true
            spacing: 0

            Sidebar {
                id: sidebar
                Layout.fillHeight: true
                onAuditLogAction:       root.openAuditLog()
                onChangePasswordAction: root.openChangePw()
                onHealthDashboardAction: root.openHealthDashboard()
                onRecoveryKeysAction:   root.openRecoveryKeys()
                onFilterChanging: searchField.text = ""
            }

            EntryTable {
                id: entryTable
                Layout.fillWidth:  true
                Layout.fillHeight: true
                onEditRequested:   (id) => openEntry(id)
                onDeleteRequested: (id) => {
                    deleteConfirm.targetId   = id
                    deleteConfirm.targetName = entryTable.selectedSiteName
                    deleteConfirm.open()
                }
            }
        }

        // ── Status bar ────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 28
            color:  Theme.bgSurface

            Rectangle {
                anchors.top:   parent.top
                anchors.left:  parent.left
                anchors.right: parent.right
                height: 1; color: Theme.bgBorder
            }
            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                spacing: 8

                // Connection status dot
                Rectangle {
                    width: 7; height: 7; radius: 4
                    color: Theme.success
                }
                Text {
                    id: statusText
                    Layout.fillWidth: true
                    text:  vault.dbPath
                    color: Theme.textMuted
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeXS
                    elide:          Text.ElideMiddle
                    maximumLineCount: 1
                }
                Text {
                    text:  vault.entryCount + " entries"
                    color: Theme.textMuted
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeXS
                }
            }
        }
    }

    // ── Bridge event handlers ─────────────────
    Connections {
        target: vault
        function onStatusMessage(text, colour) {
            statusText.text  = text
            statusText.color = colour
            statusResetTimer.restart()
        }
    }

    Timer {
        id: statusResetTimer
        interval: 4000
        onTriggered: {
            statusText.text  = vault.dbPath
            statusText.color = Theme.textMuted
        }
    }

    // ── Dialog helpers ────────────────────────
    function _createDialog(qmlFile) {
        var comp = Qt.createComponent(qmlFile)
        if (comp.status !== Component.Ready) {
            console.error("Failed to load", qmlFile, ":", comp.errorString())
            return null
        }
        var obj = comp.createObject(root)
        if (!obj) {
            console.error("createObject returned null for", qmlFile)
            return null
        }
        return obj
    }

    function openEntry(id) {
        if (!_entryDlg) _entryDlg = _createDialog("EntryDialog.qml")
        if (!_entryDlg) return
        _entryDlg.editId = (id !== null) ? id : -1
        _entryDlg.open()
    }

    function editSelected() {
        var id = entryTable.selectedId
        if (id >= 0) openEntry(id)
    }

    function deleteSelected() {
        var id = entryTable.selectedId
        if (id < 0) return
        deleteConfirm.targetId   = id
        deleteConfirm.targetName = entryTable.selectedSiteName
        deleteConfirm.open()
    }

    function copyPw() {
        var id = entryTable.selectedId
        if (id >= 0) vault.copyPassword(id)
    }

    function revealPw() {
        var id = entryTable.selectedId
        if (id >= 0) vault.revealPassword(id)
    }

    function openGen() {
        if (!_genDlg) _genDlg = _createDialog("PasswordGenDialog.qml")
        if (!_genDlg) return
        _genDlg.open()
    }

    function openBackup() {
        if (!_backupDlg) _backupDlg = _createDialog("BackupDialog.qml")
        if (!_backupDlg) return
        _backupDlg.open()
    }

    function openAuditLog() {
        if (!_auditDlg) _auditDlg = _createDialog("AuditLogDialog.qml")
        if (!_auditDlg) return
        _auditDlg.open()
    }

    function openChangePw() {
        if (!_changePwDlg) _changePwDlg = _createDialog("ChangePasswordDialog.qml")
        if (!_changePwDlg) return
        _changePwDlg.open()
    }

    function openHealthDashboard() {
        if (!_healthDlg) _healthDlg = _createDialog("HealthDashboard.qml")
        if (!_healthDlg) return
        _healthDlg.open()
    }

    function openRecoveryKeys() {
        if (!_recoveryDlg) _recoveryDlg = _createDialog("RecoveryDialog.qml")
        if (!_recoveryDlg) return
        _recoveryDlg.showRecoveryFlow = false
        _recoveryDlg.open()
    }

    function importCsv() {
        csvDlg.open()
    }

    // ── Delete confirmation ───────────────────
    Popup {
        id: deleteConfirm
        property int    targetId:   -1
        property string targetName: ""

        modal:  true
        anchors.centerIn: Overlay.overlay
        padding: 0

        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animNormal } }
        exit:  Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.animFast  } }

        Overlay.modal: Rectangle { color: Theme.bgOverlay }

        background: Rectangle {
            radius: Theme.radiusLG
            color:  Theme.bgSurface
            border.color: Theme.bgBorder
        }

        contentItem: ColumnLayout {
            width: 400
            spacing: 0

            // Header
            Rectangle {
                Layout.fillWidth: true
                height: 56
                color: Theme.bgSurface2
                radius: Theme.radiusLG
                Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: Theme.bgBorder }

                RowLayout {
                    anchors { fill: parent; leftMargin: 20; rightMargin: 16 }
                    spacing: 10
                    Rectangle {
                        width: 28; height: 28; radius: 14
                        color: Theme.dangerBg
                        Text { anchors.centerIn: parent; text: "🗑"; font.pointSize: 12 }
                    }
                    Text {
                        text:  "Delete Entry"
                        color: Theme.danger
                        font.family:    Theme.fontFamily
                        font.pointSize: Theme.fontSizeLG
                        font.weight:    Font.DemiBold
                    }
                }
            }

            ColumnLayout {
                Layout.margins: Theme.spacingLG
                spacing: Theme.spacingMD

                Text {
                    Layout.fillWidth: true
                    text:  "Delete <b>" + deleteConfirm.targetName + "</b>?<br>This action cannot be undone."
                    color: Theme.textPrimary
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeMD
                    wrapMode: Text.Wrap
                    textFormat: Text.RichText
                    lineHeight: 1.4
                }

                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }

                    // Cancel
                    SvButton {
                        text: "Cancel"
                        onClicked: deleteConfirm.close()
                    }

                    // Delete
                    SvButton {
                        text: "🗑 Delete"
                        variant: "danger"
                        onClicked: { vault.deleteEntry(deleteConfirm.targetId); deleteConfirm.close() }
                    }
                }
            }
        }
    }

    // ── CSV file dialog ───────────────────────
    FileDialog {
        id: csvDlg
        title:        "Import CSV"
        nameFilters:  ["CSV Files (*.csv)", "All Files (*)"]
        fileMode:     FileDialog.OpenFile
        onAccepted: {
            var path = root.urlToPath(selectedFile)
            var result = vault.importCsv(path)
            importResultDlg.result = result
            importResultDlg.open()
        }
    }

    // Import result popup
    Popup {
        id: importResultDlg
        property var result: ({})
        modal: true
        anchors.centerIn: Overlay.overlay
        padding: Theme.spacingLG
        Overlay.modal: Rectangle { color: Theme.bgOverlay }
        background: Rectangle { radius: Theme.radiusLG; color: Theme.bgSurface; border.color: Theme.bgBorder }
        contentItem: ColumnLayout {
            width: 360; spacing: Theme.spacingMD

            RowLayout {
                spacing: 10
                Rectangle {
                    width: 28; height: 28; radius: 14
                    color: Theme.successBg
                    Text { anchors.centerIn: parent; text: "✓"; color: Theme.success; font.pointSize: 12; font.weight: Font.Bold }
                }
                Text {
                    text:  "Import Complete"
                    color: Theme.textPrimary
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeLG
                    font.weight:    Font.DemiBold
                }
            }
            Text {
                Layout.fillWidth: true
                text: "Imported: " + (importResultDlg.result.success || 0) + "\n"
                    + "Skipped (duplicates): " + (importResultDlg.result.skipped || 0)
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeMD
                wrapMode: Text.Wrap
                lineHeight: 1.4
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                SvButton {
                    text: "Done"
                    variant: "primary"
                    onClicked: importResultDlg.close()
                }
            }
        }
    }

    // ── Toolbar button ────────────────────────
    component ToolBtn: Rectangle {
        property string label:     ""
        property string fullLabel: ""
        property string tip:       ""
        property bool   isDanger:  false
        signal clicked()

        implicitHeight: 32
        implicitWidth:  btnContent.implicitWidth + 18
        radius:   Theme.radiusSM
        color:    ma.containsMouse ? (isDanger ? Theme.dangerBg : Theme.bgSurface2) : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.animFast } }

        RowLayout {
            id: btnContent
            anchors.centerIn: parent
            spacing: 4
            Text {
                text:  label
                font.pointSize: Theme.fontSizeSM
            }
            Text {
                visible: fullLabel !== ""
                text:  fullLabel
                color: isDanger ? Theme.danger : Theme.textSecondary
                font.family:    Theme.fontFamily
                font.pointSize: Theme.fontSizeXS
                font.weight:    Font.Medium
            }
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape:  Qt.PointingHandCursor
            onClicked:    parent.clicked()
        }

        ToolTip {
            visible: ma.containsMouse && tip !== ""
            text:    tip
            delay:   600
        }
    }

    // ── Toolbar separator ─────────────────────
    component ToolSep: Rectangle {
        width: 1; height: 24; color: Theme.bgBorder; opacity: 0.6
        Layout.leftMargin: 4; Layout.rightMargin: 4
    }
}
