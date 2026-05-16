// qml/EntryTable.qml
// ───────────────────
// Main credential list view.
//
// Security: the password column always shows "••••••••".
//           RevealedRole flips to plaintext for 5 s via VaultBridge.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

Item {
    id: root
    signal editRequested(int entryId)
    signal deleteRequested(int entryId)

    // ── Current selection ─────────────────────
    property int    selectedId:       -1
    property string selectedSiteName: ""
    property int    _selectedRow:     -1

    // ── Column geometry ───────────────────────
    readonly property var colWidths: [200, 160, 110, 200, 110, 90, 90]
    readonly property var colNames:  ["Site", "Username", "Password", "URL", "Category", "Tags", "Modified"]

    Connections {
        target: vault
        function onEntriesChanged() {
            root.selectedId       = -1
            root.selectedSiteName = ""
            root._selectedRow     = -1
        }
    }

    property bool _isFiltered: vault.currentFilter !== "all" || root._hasSearchText
    property bool _hasSearchText: false

    // ── Empty state ───────────────────────────
    ColumnLayout {
        anchors.centerIn: parent
        visible:    vault.entryCount === 0 && !vault.isLocked
        spacing: 12

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root._isFiltered ? "🔍" : "🛡"
            font.pointSize: 36
            opacity: 0.4
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text:       root._isFiltered
                        ? "No entries match your filter"
                        : "Your vault is empty"
            color:      Theme.textSecondary
            font.family:    Theme.fontFamily
            font.pointSize: Theme.fontSizeLG
            font.weight: Font.DemiBold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: !root._isFiltered
            text:  "Click ➕ Add or press Ctrl+N to create your first entry"
            color: Theme.textMuted
            font.family:    Theme.fontFamily
            font.pointSize: Theme.fontSizeSM
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ─────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height:  38
            color:   Theme.bgSurface

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left:   parent.left
                anchors.right:  parent.right
                height: 1; color: Theme.bgBorder
            }

            Row {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14 }

                Repeater {
                    model: root.colNames
                    Text {
                        width:           root.colWidths[index]
                        text:            modelData.toUpperCase()
                        color:           Theme.textMuted
                        font.family:     Theme.fontFamily
                        font.pointSize:  Theme.fontSizeXS
                        font.weight:     Font.Bold
                        font.letterSpacing: 1.0
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        // ── Rows ────────────────────────────────
        ScrollView {
            Layout.fillWidth:  true
            Layout.fillHeight: true
            clip:              true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ListView {
                id: listView
                model:   vault.entryModel
                spacing: 0
                clip:    true

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animNormal }
                    NumberAnimation { property: "y"; from: y - 10; to: y; duration: Theme.animNormal; easing.type: Easing.OutCubic }
                }
                displaced: Transition {
                    NumberAnimation { properties: "x,y"; duration: Theme.animNormal; easing.type: Easing.OutCubic }
                }
                remove: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.animFast }
                }

                delegate: EntryRow {}
            }
        }
    }

    // ── Context menu ──────────────────────────
    Menu {
        id: contextMenu
        background: Rectangle {
            implicitWidth: 220
            color:  Theme.bgSurface
            border.color: Theme.bgBorder
            radius: Theme.radiusMD
        }

        MenuItem {
            text: "✏️  Edit"
            onTriggered: root.editRequested(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.bgBorder; opacity: 0.5 } }
        MenuItem {
            text: "📋  Copy Password"
            onTriggered: vault.copyPassword(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuItem {
            text: "📋  Copy Username"
            onTriggered: vault.copyUsername(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuItem {
            text: "🔗  Copy URL"
            onTriggered: vault.copyUrl(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuItem {
            text: "👁  Reveal Password (5 s)"
            onTriggered: vault.revealPassword(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.bgBorder; opacity: 0.5 } }
        MenuItem {
            text: "☆  Toggle Favourite"
            onTriggered: vault.toggleFavorite(root.selectedId)
            contentItem: MenuText { text: parent.text }
            background:  MenuBg {}
        }
        MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.bgBorder; opacity: 0.5 } }
        MenuItem {
            text: "🗑  Delete"
            onTriggered: root.deleteRequested(root.selectedId)
            contentItem: MenuText { text: parent.text; color: Theme.danger }
            background:  MenuBg {}
        }
    }

    // ── Entry row delegate ────────────────────
    component EntryRow: Rectangle {
        id: row
        required property int    index
        required property int    entryId
        required property string siteName
        required property string username
        required property string password
        required property string url
        required property string tags
        required property string category
        required property bool   favorite
        required property string modifiedAt
        required property bool   revealed

        width:   ListView.view.width
        height:  44
        color: {
            if (root._selectedRow === row.index) return Theme.cyanBg
            if (rowMa.containsMouse) return Theme.bgSurface2
            return row.index % 2 === 0 ? Theme.bgSurface : Theme.bgBase
        }
        Behavior on color { ColorAnimation { duration: Theme.animFast } }

        // Bottom border
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left:   parent.left
            anchors.right:  parent.right
            height: 1; color: Theme.bgBorder; opacity: 0.3
        }

        // Favourite indicator
        Rectangle {
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width:  3; radius: 2
            color:  row.favorite ? "#eab308" : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animFast } }
        }

        Row {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14 }

            // Favicon + Site name
            Row {
                width: root.colWidths[0]
                spacing: 8

                // Favicon in rounded container
                Rectangle {
                    width: 26; height: 26; radius: 6
                    color: Theme.bgSurface2
                    anchors.verticalCenter: parent.verticalCenter

                    Image {
                        width: 18; height: 18
                        anchors.centerIn: parent
                        source: row.url ? "image://favicon/" + row.url : "image://favicon/" + row.siteName
                        smooth: true
                    }
                }

                Text {
                    id: siteNameText
                    width:           root.colWidths[0] - 38
                    text:            row.siteName
                    color:           Theme.textPrimary
                    font.family:     Theme.fontFamily
                    font.pointSize:  Theme.fontSizeSM
                    font.weight:     Font.Medium
                    elide:           Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                    anchors.verticalCenter: parent.verticalCenter
                    
                    MouseArea {
                        id: siteNameMa
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                    ToolTip.visible: siteNameMa.containsMouse && siteNameText.truncated
                    ToolTip.text: row.siteName
                }
            }

            Text {
                width:           root.colWidths[1]
                text:            row.username
                color:           Theme.textSecondary
                font.family:     Theme.fontFamily
                font.pointSize:  Theme.fontSizeSM
                elide:           Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }

            // Password — monospace when revealed
            Text {
                width:           root.colWidths[2]
                text:            row.password
                color:           row.revealed ? Theme.textPrimary : Theme.textMuted
                font.family:     row.revealed ? "Consolas, Courier New, monospace" : Theme.fontFamily
                font.pointSize:  Theme.fontSizeSM
                elide:           Text.ElideRight
                verticalAlignment: Text.AlignVCenter
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
            }

            // URL
            Text {
                width:           root.colWidths[3]
                text:            row.url
                color:           Theme.cyan
                font.family:     Theme.fontFamily
                font.pointSize:  Theme.fontSizeXS
                elide:           Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }

            // Category — as pill badge
            Item {
                width: root.colWidths[4]
                height: parent.height
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: row.category !== ""
                    width: catText.implicitWidth + 14; height: 22; radius: 11
                    color: Theme.cyanBg
                    border.color: Theme.cyanBorder
                    Text {
                        id: catText
                        anchors.centerIn: parent
                        text: row.category
                        color: Theme.cyan
                        font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeXS
                        font.weight: Font.Medium
                    }
                }
            }

            Text {
                width:           root.colWidths[5]
                text:            row.tags
                color:           Theme.textMuted
                font.family:     Theme.fontFamily
                font.pointSize:  Theme.fontSizeXS
                elide:           Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                width:           root.colWidths[6]
                text:            row.modifiedAt
                color:           Theme.textMuted
                font.family:     Theme.fontFamily
                font.pointSize:  Theme.fontSizeXS
                verticalAlignment: Text.AlignVCenter
            }
        }

        MouseArea {
            id: rowMa
            anchors.fill:    parent
            hoverEnabled:    true
            acceptedButtons: Qt.LeftButton | Qt.RightButton

            onClicked: (mouse) => {
                root._selectedRow     = row.index
                root.selectedId       = row.entryId
                root.selectedSiteName = row.siteName
                if (mouse.button === Qt.RightButton)
                    contextMenu.popup()
            }

            onDoubleClicked: root.editRequested(row.entryId)
        }
    }

    // ── Menu text / bg sub-components ─────────
    component MenuText: Text {
        leftPadding:    14
        rightPadding:   14
        topPadding:     8
        bottomPadding:  8
        color:          Theme.textPrimary
        font.family:    Theme.fontFamily
        font.pointSize: Theme.fontSizeSM
        verticalAlignment: Text.AlignVCenter
    }

    component MenuBg: Rectangle {
        implicitWidth: 220; implicitHeight: 36
        color:  parent.highlighted ? Theme.cyanBg : "transparent"
        radius: Theme.radiusSM
        Behavior on color { ColorAnimation { duration: Theme.animFast } }
    }
}
