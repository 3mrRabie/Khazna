// qml/AuditLogDialog.qml
// ──────────────────────
// Timeline view of vault activity.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Popup {
    id: root
    anchors.centerIn: parent
    width: 680; height: 560
    modal: true; dim: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onAboutToShow: vault.refreshAuditLogs()

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        color: Theme.bgBase; radius: Theme.radiusLG
        border.color: Theme.bgBorder; border.width: 1
    }

    contentItem: ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 16

        // ── Header ─────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                width: 36; height: 36; radius: 8
                color: Theme.bgSurface3
                Text { anchors.centerIn: parent; text: "📋"; font.pointSize: 16 }
            }
            Item { width: 8 }
            Text {
                text: "Audit Log"
                color: Theme.textPrimary; font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeH2; font.weight: Font.Bold
            }
            Item { Layout.fillWidth: true }
            
            // Export Button — vault.exportAuditLog() is a real @Slot that
            // writes a timestamped CSV to the vault directory and emits
            // statusMessage (success) or errorOccurred (failure).
            SvButton {
                text: "Export CSV"
                onClicked: vault.exportAuditLog()
            }
            
            Rectangle {
                width: 32; height: 32; radius: 16
                color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                Text { anchors.centerIn: parent; text: "✕"; color: Theme.textMuted; font.pointSize: 14 }
                MouseArea { id: closeMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true; onClicked: root.close() }
            }
        }

        // ── Timeline List ─────────────────────────
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            color: Theme.bgSurface; radius: Theme.radiusMD
            border.color: Theme.bgBorder
            
            ListView {
                id: logList
                anchors { fill: parent; margins: 12 }
                clip: true; spacing: 0
                model: vault.auditModel

                delegate: Item {
                    required property int    index
                    required property string timestamp
                    required property string eventType
                    required property string description
                    required property bool   success

                    width: logList.width; height: 60

                    // Timeline vertical line
                    Rectangle {
                        anchors.left: parent.left; anchors.leftMargin: 15
                        anchors.top: parent.top; anchors.bottom: parent.bottom
                        width: 2; color: Theme.bgBorder
                        visible: index !== logList.count - 1
                    }

                    // Timeline dot
                    Rectangle {
                        anchors.left: parent.left; anchors.leftMargin: 11
                        anchors.top: parent.top; anchors.topMargin: 20
                        width: 10; height: 10; radius: 5
                        color: success ? Theme.success : Theme.danger
                        border.color: Theme.bgSurface; border.width: 2
                    }

                    RowLayout {
                        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: 36; rightMargin: 12 }
                        spacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            RowLayout {
                                spacing: 8
                                Text {
                                    text: eventType
                                    color: success ? Theme.success : Theme.danger
                                    font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.DemiBold
                                }
                                Text {
                                    text: "•"
                                    color: Theme.textMuted; font.pointSize: 8
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: description
                                    color: Theme.textSecondary
                                    font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: timestamp
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeXS
                                }
                            }
                            // Details (optional, can be empty now since description covers it)
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: logList.count === 0
                    text: "No activity recorded yet."
                    color: Theme.textMuted; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeMD
                }
            }
        }
    }

    function _getDotColor(act) {
        act = act.toLowerCase()
        if (act.indexOf("add") >= 0 || act.indexOf("create") >= 0) return Theme.success
        if (act.indexOf("delete") >= 0 || act.indexOf("remove") >= 0) return Theme.danger
        if (act.indexOf("update") >= 0 || act.indexOf("edit") >= 0) return Theme.warning
        if (act.indexOf("fail") >= 0) return Theme.danger
        return Theme.accent
    }
}
