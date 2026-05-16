// qml/HealthDashboard.qml
// ───────────────────────
// Password health overview with score gauge, issue breakdown, and issue list.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

Popup {
    id: root
    anchors.centerIn: parent
    width: 780; height: 600
    modal: true; dim: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onAboutToShow: vault.refreshHealth()

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        color: Theme.bgBase; radius: Theme.radiusLG
        border.color: Theme.bgBorder; border.width: 1
    }

    contentItem: ColumnLayout {
        anchors { fill: parent; margins: 32 }
        spacing: 28

        // ── Header ─────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                width: 36; height: 36; radius: 8
                color: Theme.cyanBg
                Text { anchors.centerIn: parent; text: "🛡"; font.pointSize: 16 }
            }
            Item { width: 8 }
            Text {
                text: "Health Dashboard"
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

        // ── Score gauge & Summary ─────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 140
            radius: Theme.radiusLG
            color: Theme.bgSurface
            border.color: Theme.bgBorder
            
            RowLayout {
                anchors { fill: parent; margins: 20 }
                spacing: 32

                // Score Ring
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: 100; height: 100; radius: 50
                    color: "transparent"
                    border.width: 8
                    border.color: vault.healthScore >= 80 ? Theme.success
                                : vault.healthScore >= 50 ? Theme.warning : Theme.danger

                    // Subtle glow
                    Rectangle {
                        anchors.fill: parent; anchors.margins: -4; radius: parent.radius + 4
                        color: "transparent"; border.width: 1
                        border.color: vault.healthScore >= 80 ? Theme.successBorder
                                    : vault.healthScore >= 50 ? Theme.warningBorder : Theme.dangerBorder
                    }

                    Text {
                        anchors.centerIn: parent
                        text: vault.healthScore + "%"
                        color: Theme.textPrimary; font.family: Theme.fontFamily
                        font.pointSize: 24; font.weight: Font.Bold
                    }
                }

                // Summary Text & Badges
                ColumnLayout {
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 12
                    Text {
                        text: vault.healthScore >= 80 ? "Your vault is in great shape!"
                            : vault.healthScore >= 50 ? "Some passwords need your attention."
                            : "Your vault has critical security issues."
                        color: Theme.textPrimary; font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeLG; font.weight: Font.DemiBold
                    }

                    RowLayout {
                        spacing: 12
                        StatBadge { label: "Weak";   count: vault.weakCount;   severity: "high" }
                        StatBadge { label: "Old";    count: vault.oldCount;    severity: "medium" }
                    }
                }
                
                Item { Layout.fillWidth: true }
            }
        }

        // ── Issue list ────────────────────────────
        Text {
            text: "Issues (" + vault.healthIssueCount + ")"
            color: Theme.textMuted; font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeSM; font.weight: Font.Bold
            font.letterSpacing: 1.0; font.capitalization: Font.AllUppercase
        }

        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            color: Theme.bgSurface; radius: Theme.radiusMD
            border.color: Theme.bgBorder
            
            ListView {
                id: issueList
                anchors { fill: parent; margins: 8 }
                clip: true; spacing: 4
                model: vault.healthModel

                delegate: Rectangle {
                    required property int entryId
                    required property string siteName
                    required property string issueType
                    required property string severity
                    required property string description

                    width: issueList.width; height: 50; radius: Theme.radiusSM
                    color: iMa.containsMouse ? Theme.bgSurface3 : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.animFast } }

                    RowLayout {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 16 }
                        spacing: 12

                        // Severity Dot
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: severity === "high" ? Theme.danger
                                 : severity === "medium" ? Theme.warning : Theme.textMuted
                            
                            // Glow for high severity
                            Rectangle {
                                anchors.fill: parent; radius: 5; visible: severity === "high"
                                color: "transparent"; border.color: Theme.dangerBorder; border.width: 2; anchors.margins: -2
                            }
                        }
                        
                        // Site
                        Text {
                            Layout.preferredWidth: 160
                            text: siteName; color: Theme.textPrimary
                            font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeMD; font.weight: Font.Medium
                            elide: Text.ElideRight
                        }
                        
                        // Issue Type Pill
                        Rectangle {
                            width: typeLabel.implicitWidth + 16; height: 24; radius: 12
                            color: issueType === "weak" ? Theme.dangerBg : Theme.warningBg
                            border.color: issueType === "weak" ? Theme.dangerBorder : Theme.warningBorder
                            border.width: 1
                            Text {
                                id: typeLabel; anchors.centerIn: parent
                                text: issueType.charAt(0).toUpperCase() + issueType.slice(1)
                                color: issueType === "weak" ? Theme.danger : Theme.warning
                                font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeXS; font.weight: Font.DemiBold
                            }
                        }
                        
                        // Description
                        Text {
                            Layout.fillWidth: true
                            text: description; color: Theme.textSecondary
                            font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                            elide: Text.ElideRight
                        }
                    }
                    
                    MouseArea {
                        id: iMa; anchors.fill: parent; hoverEnabled: true
                        // Ideally we'd trigger an edit here, but keep it simple for now
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: issueList.count === 0
                    text: "✅ No issues found — your passwords are secure!"
                    color: Theme.success; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeMD
                }
            }
        }
    }

    component StatBadge: Rectangle {
        property string label: ""
        property int count: 0
        property string severity: "low"

        width: badgeRow.implicitWidth + 24; height: 32; radius: 16
        color: count > 0
            ? (severity === "high" ? Theme.dangerBg : Theme.warningBg)
            : Theme.successBg
        border.color: count > 0
            ? (severity === "high" ? Theme.dangerBorder : Theme.warningBorder)
            : Theme.successBorder
        border.width: 1

        RowLayout {
            id: badgeRow; anchors.centerIn: parent; spacing: 6
            Text {
                text: count
                color: count > 0 ? (severity === "high" ? Theme.danger : Theme.warning) : Theme.success
                font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.Bold
            }
            Text {
                text: label
                color: Theme.textSecondary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeXS
            }
        }
    }
}
