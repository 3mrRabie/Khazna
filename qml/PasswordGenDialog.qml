// qml/PasswordGenDialog.qml
// ─────────────────────────
// Password generator with sliders, toggles, and live strength preview.
//
// FIXES:
//  - Removed onEntropyCalculated handler (no such signal on VaultBridge).
//  - Changed copyToClipboard call to vault.copyToClipboard() which now exists.
//  - Guarded onAboutToShow with Qt.callLater() so all toggle children exist
//    before the first generation is triggered (fixes "checked of null").
//  - Removed Insufficient arguments issue by ensuring all 7 args are passed.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Popup {
    id: root

    property bool inlineMode: false

    modal:  !inlineMode
    dim:    !inlineMode
    closePolicy: Popup.CloseOnEscape | (inlineMode ? Popup.NoAutoClose : Popup.CloseOnPressOutside)
    anchors.centerIn: inlineMode ? parent : Overlay.overlay
    width:  420
    padding: 0

    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        radius: Theme.radiusLG
        color:  Theme.bgSurface
        border.color: Theme.bgBorder
        Rectangle {
            anchors.fill: parent; anchors.margins: -1; radius: parent.radius + 1
            color: "transparent"; border.color: Theme.accentGlow; border.width: 1; z: -1
        }
    }

    signal usePassword(string pw)

    // Guard: use Qt.callLater so all child components are created before we
    // try to read their .checked property.
    onAboutToShow: Qt.callLater(function() {
        _regenerate()
    })

    function _regenerate() {
        if (typeof lenSlider === "undefined" || lenSlider === null) return
        if (typeof upperCheck === "undefined" || upperCheck === null) return
        if (typeof lowerCheck === "undefined" || lowerCheck === null) return
        if (typeof numCheck === "undefined" || numCheck === null) return
        if (typeof symCheck === "undefined" || symCheck === null) return
        vault.generatePassword(
            lenSlider.value,
            upperCheck.checked, lowerCheck.checked,
            numCheck.checked,   symCheck.checked,
            false, ""
        )
    }

    Connections {
        target: vault
        function onPasswordGenerated(pw) { if (root.visible) pwText.text = pw }
        // NOTE: onEntropyCalculated removed — VaultBridge does not emit this signal.
    }

    contentItem: ColumnLayout {
        spacing: 0

        // ── Header ─────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; height: 50
            color: Theme.bgSurface2; radius: Theme.radiusLG
            Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: Theme.bgBorder }

            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 12 }
                Text { text: "⚡"; font.pointSize: 14 }
                Text {
                    text: "Generate Password"
                    color: Theme.textPrimary; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeMD; font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Rectangle {
                    width: 28; height: 28; radius: 14
                    color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                    Text { anchors.centerIn: parent; text: "✕"; color: Theme.textMuted; font.pointSize: 12 }
                    MouseArea { id: closeMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
                }
            }
        }

        ColumnLayout {
            Layout.margins: 20
            spacing: 18

            // ── Password Preview ───────────────────
            Rectangle {
                Layout.fillWidth: true; height: 56; radius: Theme.radiusMD
                color: Theme.bgBase; border.color: Theme.bgBorder

                RowLayout {
                    anchors { fill: parent; leftMargin: 16; rightMargin: 8 }
                    spacing: 8

                    Text {
                        id: pwText
                        Layout.fillWidth: true
                        color: Theme.accent
                        font.family: "Consolas, Courier New, monospace"
                        font.pointSize: 15
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        width: 34; height: 34; radius: Theme.radiusSM
                        color: copyMa.containsMouse ? Theme.bgSurface2 : "transparent"
                        Text { anchors.centerIn: parent; text: "📋"; font.pointSize: 13 }
                        MouseArea {
                            id: copyMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                            onClicked: {
                                vault.copyToClipboard(pwText.text)
                                if (!root.inlineMode) root.close()
                            }
                        }
                        ToolTip.visible: copyMa.containsMouse; ToolTip.text: "Copy"
                    }

                    Rectangle {
                        width: 34; height: 34; radius: Theme.radiusSM
                        color: refreshMa.containsMouse ? Theme.bgSurface2 : "transparent"
                        Text { anchors.centerIn: parent; text: "🔄"; font.pointSize: 13 }
                        MouseArea {
                            id: refreshMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                            onClicked: root._regenerate()
                        }
                        ToolTip.visible: refreshMa.containsMouse; ToolTip.text: "Regenerate"
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.bgBorder; opacity: 0.5 }

            // ── Length control ─────────────────────
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Length"; color: Theme.textPrimary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeMD }
                Item { Layout.fillWidth: true }
                Text { text: lenSlider.value; color: Theme.accent; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeLG; font.weight: Font.Bold }
            }

            Slider {
                id: lenSlider
                Layout.fillWidth: true
                from: 8; to: 64; stepSize: 1; value: 20
                onValueChanged: root._regenerate()

                background: Rectangle {
                    x: lenSlider.leftPadding; y: lenSlider.topPadding + lenSlider.availableHeight / 2 - height / 2
                    implicitWidth: 200; implicitHeight: 6
                    width: lenSlider.availableWidth; height: implicitHeight; radius: 3
                    color: Theme.bgSurface3
                    Rectangle { width: lenSlider.visualPosition * parent.width; height: parent.height; color: Theme.cyan; radius: 3 }
                }
                handle: Rectangle {
                    x: lenSlider.leftPadding + lenSlider.visualPosition * (lenSlider.availableWidth - width)
                    y: lenSlider.topPadding + lenSlider.availableHeight / 2 - height / 2
                    implicitWidth: 18; implicitHeight: 18; radius: 9
                    color: lenSlider.pressed ? Theme.cyanPress : Theme.cyan
                    border.color: "#fff"; border.width: 2
                }
            }

            // ── Character class toggles ────────────
            ColumnLayout {
                Layout.fillWidth: true; spacing: 10

                GenToggle { id: upperCheck; label: "A-Z"; desc: "Uppercase letters"; checked: true }
                GenToggle { id: lowerCheck; label: "a-z"; desc: "Lowercase letters"; checked: true }
                GenToggle { id: numCheck;   label: "0-9"; desc: "Numbers";           checked: true }
                GenToggle { id: symCheck;   label: "!@#"; desc: "Special characters"; checked: true }
            }

            Item { height: 4 }

            // ── Use Button ─────────────────────────
            SvButton {
                Layout.fillWidth: true
                text: "Use Password"
                variant: "primary"
                onClicked: root.usePassword(pwText.text)
            }
        }
    }

    // ── Toggle component ──────────────────────
    component GenToggle: RowLayout {
        property string label:   ""
        property string desc:    ""
        property alias  checked: sw.checked

        Layout.fillWidth: true

        Rectangle {
            width: 38; height: 24; radius: 6; color: Theme.bgSurface3
            Text {
                anchors.centerIn: parent; text: label
                color: Theme.textSecondary
                font.family: "Consolas, Courier New, monospace"; font.pointSize: Theme.fontSizeXS
            }
        }
        Text {
            Layout.fillWidth: true; text: desc; color: Theme.textPrimary
            font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM
        }
        Switch {
            id: sw
            onCheckedChanged: root._regenerate()
        }
    }
}
