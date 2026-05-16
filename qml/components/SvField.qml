// qml/components/SvField.qml
// ──────────────────────────
// Styled text / password input field.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import ".."   // Theme

ColumnLayout {
    id: root
    spacing: 6

    property alias text:        field.text
    property alias placeholder: field.placeholderText
    property alias echoMode:    field.echoMode
    property alias readOnly:    field.readOnly
    property alias inputMethodHints: field.inputMethodHints
    property string label: ""
    property bool   showToggle: false     // show 👁 toggle for passwords
    property string accessibleName: label || placeholder

    signal accepted()
    signal textEdited(string t)

    // ── Optional label ────────────────────────
    Text {
        visible:         root.label !== ""
        text:            root.label
        color:           Theme.textSecondary
        font.family:     Theme.fontFamily
        font.pointSize:  Theme.fontSizeSM
        font.weight:     Font.Medium
    }

    // ── Input row ─────────────────────────────
    Rectangle {
        Layout.fillWidth: true
        implicitHeight:   40
        radius:           Theme.radiusMD
        color:            Theme.bgSurface
        border.color:     field.activeFocus ? Theme.accent : Theme.bgBorder
        border.width:     field.activeFocus ? 2 : 1

        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

        // Glow ring (focus)
        Rectangle {
            anchors.fill:    parent
            anchors.margins: -1
            radius:          parent.radius + 1
            color:           "transparent"
            border.color:    field.activeFocus ? Theme.accentGlow : "transparent"
            border.width:    2
            z: -1
        }

        RowLayout {
            anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
            spacing: 8

            TextField {
                id: field
                Layout.fillWidth: true
                Layout.fillHeight: true
                background:    Item {}
                color:         Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                font.family:   Theme.fontFamily
                font.pointSize:Theme.fontSizeSM
                leftPadding:   0
                rightPadding:  0
                selectByMouse: true

                Accessible.name: root.accessibleName
                Accessible.role: Accessible.EditableText

                onAccepted:    root.accepted()
                onTextChanged: root.textEdited(text)
            }

            // 👁 reveal toggle (passwords only)
            Rectangle {
                visible:         root.showToggle
                width: 24; height: 24; radius: 12
                color: toggleMa.containsMouse ? Theme.bgSurface3 : "transparent"
                Text {
                    anchors.centerIn: parent
                    text:            field.echoMode === TextInput.Password ? "👁" : "🔒"
                    font.pointSize:  12
                    color:           Theme.textSecondary
                }

                MouseArea {
                    id: toggleMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape:  Qt.PointingHandCursor
                    onClicked: {
                        field.echoMode = (field.echoMode === TextInput.Password)
                            ? TextInput.Normal
                            : TextInput.Password
                    }
                }
            }
        }
    }
}
