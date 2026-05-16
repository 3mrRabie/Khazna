// qml/EntryDialog.qml
// ────────────────────
// Modal dialog for creating or editing a vault entry.
//
// Security: password text is placed in an echoMode=Password field.
// vault.getEntry(id) is called only when the dialog opens and the
// returned map is not stored anywhere persistent.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Popup {
    id: root

    property int editId: -1   // -1 = add mode
    readonly property bool isEdit: editId >= 0

    modal:          true
    closePolicy:    Popup.CloseOnEscape
    anchors.centerIn: Overlay.overlay
    width:  600
    height: Overlay.overlay ? Math.min(implicitHeight, Overlay.overlay.height - 40) : implicitHeight
    padding: 0

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animNormal; easing.type: Easing.OutCubic }
        NumberAnimation { property: "scale";   from: 0.96; to: 1; duration: Theme.animNormal; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.animFast; easing.type: Easing.InCubic }
    }
    Overlay.modal: Rectangle { color: Theme.bgOverlay }

    background: Rectangle {
        radius: Theme.radiusLG; color: Theme.bgBase; border.color: Theme.bgBorder
    }

    onOpened: _load()
    onClosed: _clear()

    // ── Connections ───────────────────────────
    Connections {
        target: vault
        function onStrengthResult(score, level, colour, tips) {
            if (root.visible) strengthBar.setStrength(score, level, colour, tips)
        }
        function onPasswordGenerated(pw) {
            if (root.visible) pwField.text = pw
        }
    }

    contentItem: ColumnLayout {
        spacing: 0
        implicitWidth: root.width

        // ── Header ──────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 60; color: Theme.bgSurface; radius: Theme.radiusLG
            Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: Theme.bgBorder }
            
            RowLayout {
                anchors { fill: parent; leftMargin: 24; rightMargin: 16 }
                spacing: 12
                
                Rectangle {
                    width: 32; height: 32; radius: 8
                    color: Theme.bgSurface3
                    Text { anchors.centerIn: parent; text: root.isEdit ? "✏️" : "➕"; font.pointSize: 14 }
                }
                
                Text {
                    text:  root.isEdit ? "Edit Entry" : "New Entry"
                    color: Theme.textPrimary; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLG; font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                
                Rectangle {
                    width: 28; height: 28; radius: 14
                    color: closeMa.containsMouse ? Theme.bgSurface3 : "transparent"
                    Text { anchors.centerIn: parent; text: "✕"; color: Theme.textMuted; font.pointSize: 14 }
                    MouseArea { id: closeMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
                }
            }
        }

        // ── Form ────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            padding: Theme.spacingLG

            ColumnLayout {
                id: formLayout
                width: parent.width - (Theme.spacingLG * 2)
                spacing: Theme.spacingLG

                // SECTION: General
                SectionLabel { text: "General" }
                
                SvField { id: siteField;     label: "Site name *";  placeholder: "e.g. GitHub";             Layout.fillWidth: true }
                SvField { id: urlField;      label: "URL";           placeholder: "https://github.com";      Layout.fillWidth: true }
                SvField { id: usernameField; label: "Username";      placeholder: "your@email.com";          Layout.fillWidth: true }

                // SECTION: Security
                SectionDivider {}
                SectionLabel { text: "Security" }

                // Password row
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: "Password *"; color: Theme.textSecondary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.Medium }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle {
                            Layout.fillWidth: true
                            height: 40; radius: Theme.radiusMD
                            color:  Theme.bgSurface
                            border.color: pwField.activeFocus ? Theme.accent : Theme.bgBorder
                            border.width: pwField.activeFocus ? 2 : 1
                            Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                            RowLayout {
                                anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
                                spacing: 0
                                TextField {
                                    id: pwField
                                    Layout.fillWidth:  true
                                    Layout.fillHeight: true
                                    background:     Item {}
                                    color:          Theme.textPrimary
                                    placeholderText: "Enter or generate a password"
                                    placeholderTextColor: Theme.textMuted
                                    font.family:    Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                                    echoMode:       TextInput.Password
                                    leftPadding: 0; rightPadding: 0; selectByMouse: true
                                    Accessible.name: "Password"
                                    onTextChanged: {
                                        if (text) vault.checkStrength(text)
                                        breachBox.visible = false   // clear stale result
                                    }
                                }
                                Text {
                                    text: pwField.echoMode === TextInput.Password ? "👁" : "🔒"
                                    color: Theme.textMuted; font.pointSize: Theme.fontSizeMD
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: pwField.echoMode = pwField.echoMode === TextInput.Password ? TextInput.Normal : TextInput.Password }
                                }
                            }
                        }

                        // Generate Button
                        Rectangle {
                            height: 40; width: 120; radius: Theme.radiusMD
                            color: genMa.containsMouse ? Theme.cyanHover : Theme.cyanBg
                            border.color: Theme.cyan
                            Behavior on color { ColorAnimation { duration: Theme.animFast } }
                            RowLayout {
                                anchors.centerIn: parent; spacing: 6
                                Text { text: "⚡"; color: genMa.containsMouse ? "#fff" : Theme.cyan; font.pointSize: 12 }
                                Text { text: "Generate"; color: genMa.containsMouse ? "#fff" : Theme.cyan; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.DemiBold }
                            }
                            MouseArea { id: genMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                                onClicked: genPopup.open() }
                        }

                        // Breach Check Button — calls vault.checkBreachPassword()
                        // and reveals the breachBox result row below.
                        Rectangle {
                            id: breachBtn
                            height: 40; width: 40; radius: Theme.radiusMD
                            color: breachMa.containsMouse ? Theme.bgSurface3 : Theme.bgSurface2
                            border.color: breachMa.containsMouse ? Theme.cyan : Theme.bgBorder
                            Behavior on color { ColorAnimation { duration: Theme.animFast } }
                            Text { anchors.centerIn: parent; text: "🔍"; font.pointSize: 14 }
                            MouseArea {
                                id: breachMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!pwField.text) return
                                    var result = vault.checkBreachPassword(pwField.text)
                                    if (result.error && result.error !== "") {
                                        breachBox.breached  = false
                                        breachBox.errorText = result.error
                                    } else {
                                        breachBox.breached  = result.is_breached
                                        breachBox.errorText = ""
                                    }
                                    breachBox.visible = true
                                }
                            }
                            ToolTip.visible: breachMa.containsMouse
                            ToolTip.delay: 400
                            ToolTip.text: "Check password against known breach databases (HIBP)"
                        }
                    }

                    StrengthBar { id: strengthBar; Layout.fillWidth: true }
                }

                // Breach check result — shown after the 🔍 button is pressed.
                Rectangle {
                    id: breachBox; Layout.fillWidth: true; visible: false; radius: Theme.radiusMD
                    height: breachRow.implicitHeight + 20
                    property bool   breached:  false
                    property string errorText: ""
                    color: errorText !== "" ? Theme.bgSurface2
                         : breached        ? Theme.dangerBg : Theme.successBg
                    border.color: errorText !== "" ? Theme.bgBorder
                                : breached         ? Theme.dangerBorder : Theme.successBorder
                    RowLayout {
                        id: breachRow; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 12
                        Rectangle {
                            width: 24; height: 24; radius: 12
                            color: breachBox.errorText !== "" ? Theme.textMuted
                                 : breachBox.breached ? Theme.danger : Theme.success
                            Text {
                                anchors.centerIn: parent
                                text: breachBox.errorText !== "" ? "?" : (breachBox.breached ? "!" : "✓")
                                color: Theme.textInverse; font.weight: Font.Bold
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: breachBox.errorText !== ""
                                ? "Breach check unavailable: " + breachBox.errorText
                                : breachBox.breached
                                    ? "⚠ This password appeared in a known data breach!"
                                    : "✓ Password not found in known breach databases."
                            color: breachBox.errorText !== "" ? Theme.textMuted
                                 : breachBox.breached ? Theme.danger : Theme.success
                            font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; wrapMode: Text.Wrap
                        }
                    }
                }

                // SECTION: Organization
                SectionDivider {}
                SectionLabel { text: "Organization" }

                SvField { id: tagsField;  label: "Tags";  placeholder: "comma-separated: work, social, finance"; Layout.fillWidth: true }

                // Category dropdown
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 6
                    Text { text: "Category"; color: Theme.textSecondary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.Medium }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Rectangle {
                            Layout.fillWidth: true; height: 40; radius: Theme.radiusMD
                            color: Theme.bgSurface; border.color: Theme.bgBorder
                            RowLayout {
                                anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
                                spacing: 0
                                ComboBox {
                                    id: categoryCombo
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    model: vault.getAllCategories()
                                    editable: true
                                    background: Item {}
                                    contentItem: TextInput {
                                        text: categoryCombo.editText; color: Theme.textPrimary
                                        font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                                        verticalAlignment: Text.AlignVCenter; leftPadding: 0
                                        selectByMouse: true; selectionColor: Theme.cyanBg
                                        onTextEdited: categoryCombo.editText = text
                                    }
                                    popup: Popup {
                                        y: categoryCombo.height + 4; width: categoryCombo.width
                                        padding: 0
                                        contentItem: ListView {
                                            implicitHeight: contentHeight; model: categoryCombo.delegateModel
                                            clip: true; ScrollIndicator.vertical: ScrollIndicator {}
                                        }
                                        background: Rectangle { color: Theme.bgSurface2; border.color: Theme.bgBorder; radius: Theme.radiusMD }
                                    }
                                    delegate: ItemDelegate {
                                        width: categoryCombo.width; height: 36
                                        contentItem: Text {
                                            text: modelData; color: Theme.textPrimary
                                            font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                                            verticalAlignment: Text.AlignVCenter; leftPadding: 8
                                        }
                                        background: Rectangle {
                                            color: parent.highlighted ? Theme.cyanBg : "transparent"
                                            radius: Theme.radiusXS
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Auto-detect button
                        Rectangle {
                            height: 40; width: 40; radius: Theme.radiusMD
                            color: autoDetMa.containsMouse ? Theme.bgSurface3 : Theme.bgSurface2
                            border.color: Theme.bgBorder
                            Text { anchors.centerIn: parent; text: "✨"; font.pointSize: 14 }
                            MouseArea { id: autoDetMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                                onClicked: {
                                    var detected = vault.detectCategory(urlField.text, siteField.text)
                                    var idx = categoryCombo.model.indexOf(detected)
                                    if (idx >= 0) categoryCombo.currentIndex = idx
                                }
                            }
                            ToolTip.visible: autoDetMa.containsMouse
                            ToolTip.text: "Auto-detect category"
                        }
                    }
                }

                // Notes
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 6
                    Text { text: "Notes"; color: Theme.textSecondary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.Medium }
                    Rectangle {
                        Layout.fillWidth: true; height: 80; radius: Theme.radiusMD; color: Theme.bgSurface
                        border.color: notesField.activeFocus ? Theme.accent : Theme.bgBorder
                        border.width: notesField.activeFocus ? 2 : 1
                        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                        ScrollView {
                            anchors { fill: parent; margins: 12 }
                            TextArea {
                                id: notesField
                                background:     Item {}
                                color:          Theme.textPrimary
                                placeholderText: "Optional notes…"
                                placeholderTextColor: Theme.textMuted
                                font.family:    Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                                wrapMode:       TextArea.Wrap
                                Accessible.name: "Notes"
                            }
                        }
                    }
                }

                // Favourite Toggle
                Rectangle {
                    Layout.fillWidth: true; height: 48; radius: Theme.radiusMD
                    color: Theme.bgSurface; border.color: Theme.bgBorder
                    RowLayout {
                        anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                        Text { text: "★"; color: favCheck.checked ? "#eab308" : Theme.textMuted; font.pointSize: 16 }
                        Text { Layout.fillWidth: true; text: "Mark as favourite"; color: Theme.textPrimary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM }
                        Switch {
                            id: favCheck
                            checked: false
                            // Simple custom switch indicator could go here, but native styled is okay
                        }
                    }
                }
                
                Item { height: 8 } // Bottom padding
            }
        }

        // ── Footer ──────────────────────────────
        Rectangle {
            Layout.fillWidth: true; height: 68; color: Theme.bgSurface; radius: Theme.radiusLG
            Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: Theme.bgBorder }
            RowLayout {
                anchors { fill: parent; leftMargin: 24; rightMargin: 24 }
                Item { Layout.fillWidth: true }
                
                // Cancel
                SvButton {
                    text: "Cancel"
                    onClicked: root.close()
                }
                
                // Save — primary
                SvButton {
                    text: "Save Entry"
                    variant: "primary"
                    onClicked: _save()
                }
            }
        }
    }

    // ── Components ────────────────────────────
    component SectionLabel: Text {
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pointSize: Theme.fontSizeXS
        font.weight: Font.Bold
        font.letterSpacing: 1.0
        font.capitalization: Font.AllUppercase
    }

    component SectionDivider: Rectangle {
        Layout.fillWidth: true; height: 1; color: Theme.bgBorder; opacity: 0.5
    }

    // ── Inline generator popup ────────────────
    PasswordGenDialog {
        id: genPopup
        inlineMode: true
        onUsePassword: (pw) => {
            pwField.text = pw
            close()
        }
    }

    // ── Logic ─────────────────────────────────
    function _load() {
        strengthBar.clear()
        breachBox.visible = false
        if (!root.isEdit) {
            siteField.text = ""; urlField.text = ""; usernameField.text = ""
            pwField.text = ""; tagsField.text = ""; notesField.text = ""
            favCheck.checked = false
            categoryCombo.currentIndex = 0
            return
        }
        var e = vault.getEntry(root.editId)
        if (!e || Object.keys(e).length === 0) return
        siteField.text     = e.siteName     || ""
        urlField.text      = e.url          || ""
        usernameField.text = e.username     || ""
        pwField.text       = e.password     || ""
        tagsField.text     = e.tags         || ""
        notesField.text    = e.notes        || ""
        favCheck.checked   = e.favorite     || false
        // Set category
        categoryCombo.model = vault.getAllCategories()
        var cat = e.category || "Other"
        var catIdx = categoryCombo.find(cat)
        if (catIdx >= 0) {
            categoryCombo.currentIndex = catIdx
        } else {
            categoryCombo.editText = cat
        }
        if (pwField.text) vault.checkStrength(pwField.text)
    }

    function _clear() {
        pwField.text = ""
    }

    function _save() {
        if (!siteField.text.trim()) {
            siteField.focus = true; return
        }
        if (!pwField.text) {
            pwField.focus = true; return
        }
        var cat = categoryCombo.editText || categoryCombo.currentText || "Other"
        var ok
        if (root.isEdit)
            ok = vault.updateEntry(root.editId, siteField.text.trim(), urlField.text.trim(),
                                   usernameField.text.trim(), pwField.text,
                                   notesField.text.trim(), tagsField.text.trim(), favCheck.checked, cat)
        else
            ok = vault.addEntry(siteField.text.trim(), urlField.text.trim(),
                                usernameField.text.trim(), pwField.text,
                                notesField.text.trim(), tagsField.text.trim(), favCheck.checked, cat)
        if (ok) root.close()
    }
}
