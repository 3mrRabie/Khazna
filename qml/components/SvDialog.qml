// qml/components/SvDialog.qml
// ───────────────────────────
// Dark-themed modal dialog base.  All vault dialogs inherit from this.
//
// Usage
// ─────
//   SvDialog {
//       id: myDlg
//       title: "My Dialog"
//       width: 520
//
//       // Put content inside the default slot:
//       ColumnLayout { ... }
//
//       // Bottom-right action buttons via footerContent:
//       footerContent: Row {
//           SvButton { text: "Cancel"; onClicked: myDlg.close() }
//           SvButton { text: "Save";   variant: "primary"; onClicked: ... }
//       }
//   }

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."   // Theme

Popup {
    id: root

    property string title:        ""
    property alias  footerContent: footer.data
    default property alias contentData: body.data

    modal:         true
    closePolicy:   Popup.CloseOnEscape
    anchors.centerIn: Overlay.overlay

    // ── Enter/exit animation ──────────────────
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animNormal }
        NumberAnimation { property: "scale";   from: 0.94; to: 1; duration: Theme.animNormal; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.animFast }
    }

    // ── Overlay dimming ───────────────────────
    Overlay.modal: Rectangle {
        color: "#aa000000"
    }

    // ── Panel background ──────────────────────
    background: Rectangle {
        radius: Theme.radiusLG
        color:  Theme.bgBase
        border.color: Theme.bgBorder
        border.width: 1

        // Subtle glow on accent border
        layer.enabled: true
        layer.effect: null
    }

    // ── Layout ────────────────────────────────
    padding: 0

    contentItem: ColumnLayout {
        spacing: 0
        implicitWidth:  root.width
        implicitHeight: root.height

        // Header
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color:  Theme.bgSurface
            radius: Theme.radiusLG   // top corners only; clipped by dialog

            // Bottom border
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left:   parent.left
                anchors.right:  parent.right
                height: 1
                color:  Theme.bgBorder
            }

            RowLayout {
                anchors { fill: parent; leftMargin: 24; rightMargin: 16 }

                Text {
                    text:            root.title
                    color:           Theme.textPrimary
                    font.family:     Theme.fontFamily
                    font.pointSize:  Theme.fontSizeLG
                    font.weight:     Font.DemiBold
                    Layout.fillWidth: true
                }

                Text {
                    text:            "✕"
                    color:           Theme.textMuted
                    font.pointSize:  Theme.fontSizeMD
                    MouseArea {
                        anchors.fill: parent
                        cursorShape:  Qt.PointingHandCursor
                        onClicked:    root.close()
                        hoverEnabled: true
                        onEntered:    parent.color = Theme.textPrimary
                        onExited:     parent.color = Theme.textMuted
                    }
                }
            }
        }

        // Body
        ColumnLayout {
            id: body
            Layout.fillWidth:  true
            Layout.fillHeight: true
            Layout.margins:    Theme.spacingLG
            spacing:           Theme.spacingMD
        }

        // Footer
        Rectangle {
            Layout.fillWidth: true
            height: footerVisible ? 64 : 0
            visible: footerVisible
            color:   Theme.bgSurface
            radius:  Theme.radiusLG   // bottom corners

            property bool footerVisible: footer.children.length > 0

            Rectangle {
                anchors.top:   parent.top
                anchors.left:  parent.left
                anchors.right: parent.right
                height: 1
                color:  Theme.bgBorder
            }

            Item {
                id: footer
                anchors { fill: parent; leftMargin: Theme.spacingLG; rightMargin: Theme.spacingLG }
            }
        }
    }
}
