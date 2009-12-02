#from __future__ import division
import random
import sys
import math
import os.path

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from Model import *
import LicTreeModel
import LicBinaryReader
import LicBinaryWriter
import LicTemplate
import LicPartListPage
import config
import l3p
import povray
import LicDialogs
import LicUndoActions
import Layout
import GLHelpers

from modeltest import ModelTest

__version__ = 0.1

class LicGraphicsScene(QGraphicsScene):

    PageViewContinuous = -1
    PageViewContinuousFacing = -2
        
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)
        self.reset()

    def reset(self):
        self.scaleFactor = 1.0
        self.pagesToDisplay = 1
        self.currentPage = None
        self.pages = []
        self.guides = []
        self.xSnapLine = self.createSnapLine()
        self.ySnapLine = self.createSnapLine()
        self.snapToGuides = True
        self.snapToItems = True

    def createSnapLine(self):
        snapLine = QGraphicsLineItem()
        pen = QPen(Qt.darkCyan)
        pen.setWidth(2)
        snapLine.setPen(pen)
        snapLine.setZValue(10000)  # Put on top of everything else
        snapLine.hide()
        self.addItem(snapLine)
        return snapLine

    def clearSelection(self):
        self.clearSelectedParts()
        QGraphicsScene.clearSelection(self)
        
    def clearSelectedParts(self):
        partList = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                partList.append(item)
        if partList:
            for part in partList[:-1]:
                part.setSelected(False, False)
            partList[-1].setSelected(False, True)

    def clear(self):
        QGraphicsScene.clear(self)
        self.reset()

    def drawForeground(self, painter, rect):
        GLHelpers.initFreshContext(False)

        pagesToDraw = []
        for page in self.pages:
            if page.isVisible() and rect.intersects(page.rect().translated(page.pos())):
                pagesToDraw.append(page)
                
        for page in pagesToDraw:
            page.drawGLItems(painter, rect)

        GLHelpers.setupForQtPainter()
        for page in pagesToDraw:
            page.drawAnnotations(painter, rect)
    
    def pageUp(self):
        self.clearSelection()
        if self.pages and self.currentPage:
            self.selectPage(max(self.currentPage._number - 1, self.pages[0]._number))
            self.currentPage.setSelected(True)
            self.emit(SIGNAL("sceneClick"))

    def pageDown(self):
        self.clearSelection()
        if self.pages and self.currentPage:
            self.selectPage(min(self.pages[-1]._number, self.currentPage._number + 1))
            self.currentPage.setSelected(True)
            self.emit(SIGNAL("sceneClick"))

    def selectFirstPage(self):
        self.selectPage(1)
        self.currentPage.setSelected(True)

    def selectLastPage(self):
        self.selectPage(self.pages[-1]._number)
        self.currentPage.setSelected(True)

    def selectCurrentPage(self):
        if self.currentPage:
            self.selectPage(self.currentPage._number)
            self.currentPage.setSelected(True)

    def refreshView(self):
        self.setPagesToDisplay(self.pagesToDisplay)
        
    def selectPage(self, pageNumber):
        # Don't call currentPage.setSelected() from here!  Must be done later
        for page in self.pages:
            if self.pagesToDisplay == 1 and page._number == pageNumber:
                page.setPos(0, 0)
                page.show()
                self.currentPage = page
            elif self.pagesToDisplay == 2:
                if pageNumber % 2:  # odd pages on right
                    if page._number == pageNumber:
                        page.setPos(Page.PageSize.width() + 20, 0)
                        page.show()
                        self.currentPage = page
                    elif page._number == pageNumber - 1:
                        page.show()
                        page.setPos(10, 0)
                    else:
                        page.hide()
                        page.setPos(0, 0)
                else:  # even pages on left
                    if page._number == pageNumber:
                        page.setPos(10, 0)
                        page.show()
                        self.currentPage = page
                    elif page._number == pageNumber + 1:
                        page.setPos(Page.PageSize.width() + 20, 0)
                        page.show()
                    else:
                        page.hide()
                        page.setPos(0, 0)
            elif self.pagesToDisplay == self.PageViewContinuous or self.pagesToDisplay == self.PageViewContinuousFacing:
                if page._number == pageNumber:
                    self.currentPage = page
            else:
                page.hide()
                page.setPos(0, 0)

        self.scrollToPage(self.currentPage)

    def selectionChanged(self):
        selList = self.selectedItems()
        if self.pagesToDisplay == 1 or not selList or isinstance(selList[-1], Guide):
            return
        self.scrollToPage(selList[-1].getPage())
    
    def fullItemSelectionUpdate(self, *itemList):
        self.clearSelection()
        for item in itemList:
            item.setSelected(True)
        self.emit(SIGNAL("sceneClick"))

    def scrollToPage(self, page):
        view = self.views()[0]
        view.setInteractive(False)
        view.centerOn(page)
        view.setInteractive(True)
        self.currentPage = page
        
    def showOnePage(self):
        self.pagesToDisplay = 1
        self.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        for page in self.pages:
            page.hide()
            page.setPos(0.0, 0.0)
        self.selectCurrentPage()
    
    def showTwoPages(self):
        if len(self.pages) < 2:
            return self.showOnePage()

        self.pagesToDisplay = 2
        self.setSceneRect(0, 0, (Page.PageSize.width() * 2) + 30, Page.PageSize.height() + 20)

        for page in self.pages:
            page.hide()
            page.setPos(0, 0)

        index = self.pages.index(self.currentPage)
        if self.currentPage == self.pages[-1]:
            p1 = self.pages[index - 1]
            p2 = self.currentPage
        else:
            p1 = self.currentPage
            p2 = self.pages[index + 1]
        
        p1.setPos(10, 0)
        p1.show()
        p2.setPos(Page.PageSize.width() + 20, 0)
        p2.show()
        self.selectCurrentPage()

    def continuous(self):
        self.pagesToDisplay = self.PageViewContinuous
        pc = len(self.pages)
        ph = Page.PageSize.height()
        height = (10 * (pc + 1)) + (ph * pc)
        self.setSceneRect(0, 0, Page.PageSize.width() + 20, height)
        
        for guide in self.guides:
            if guide.orientation == Layout.Vertical:
                guide.setLength(height)
                
        for i, page in enumerate(self.pages):
            page.setPos(10, (10 * (i + 1)) + (ph * i))
            page.show()
        self.selectCurrentPage()

    def continuousFacing(self):
        if len(self.pages) < 3:
            return self.continuous()
        self.pagesToDisplay = self.PageViewContinuousFacing
        pw = Page.PageSize.width()
        ph = Page.PageSize.height()
        rows = sum(divmod(len(self.pages) - 1, 2)) + 1
        width = pw + pw + 30
        height = (10 * (rows + 1)) + (ph * rows)
        self.setSceneRect(0, 0, width, height)
        
        for guide in self.guides:
            if guide.orientation == Layout.Vertical:
                guide.setLength(height)
            else:
                guide.setLength(width)
            
        self.pages[0].setPos(10, 10)  # Template page first
        self.pages[0].show()
        
        for i, page in enumerate(self.pages[1:]):
            i += 2
            x = 10 + ((pw + 10) * (i % 2))
            y = (10 * ((i // 2) + 1)) + (ph * (i // 2))
            page.setPos(x, y)
            page.show()
        self.selectCurrentPage()

    def getPagesToDisplay(self):
        return self.pagesToDisplay
    
    def setPagesToDisplay(self, pagesToDisplay):
        if pagesToDisplay == self.PageViewContinuous:
            return self.continuous()
        if pagesToDisplay == self.PageViewContinuousFacing:
            return self.continuousFacing()
        if pagesToDisplay == 2:
            return self.showTwoPages()
        return self.showOnePage()

    def addItem(self, item):
        QGraphicsScene.addItem(self, item)
        if isinstance(item, Page):
            self.pages.append(item)
            self.pages.sort(key = lambda x: x._number)
            self.setPagesToDisplay(self.pagesToDisplay)
        
    def removeItem(self, item):
        self.emit(SIGNAL("itemDeleted"), item)
        QGraphicsScene.removeItem(self, item)
        if not isinstance(item, Page):
            return
        if isinstance(item, Page) and item in self.pages:
            self.pages.remove(item)
            if self.pagesToDisplay == self.PageViewContinuous:
                self.continuous()
            elif self.pagesToDisplay == self.PageViewContinuousFacing:
                self.continuousFacing()

    def removeAllGuides(self):
        self.undoStack.beginMacro("Remove all guides")
        for guide in list(self.guides):
            self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, guide, False))
        self.undoStack.endMacro()

    def addGuide(self, orientation, pos):
        guide = Guide(orientation, self.sceneRect())
        guide.setPos(pos)
        self.guides.append(guide)
        self.addItem(guide)

    def addNewGuide(self, orientation):
        self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, Guide(orientation, self.sceneRect()), True))

    def snap(self, item):
        if not self.snapToGuides and not self.snapToItems:
            return # User disabled snap
         
        snapDistance = 20
        margin = 20

        # Hide any existing snap guide lines
        self.xSnapLine.hide()
        self.ySnapLine.hide()
        
        # Build dict of all guides and page items and their [left, right, top, bottom] points
        itemDict = {}
        
        if self.snapToGuides:
            for guide in self.guides:
                guidePt = guide.mapToScene(guide.line().p1())
                itemDict[guide] = [guidePt.x(), guidePt.y()]

        if self.snapToItems:
            for pageItem in item.getPage().getAllChildItems():
                if isinstance(pageItem, Step):
                    continue
                if item.isAncestorOf(pageItem):
                    continue
                if pageItem is item:
                    continue
                itemDict[pageItem] = pageItem.getCornerList()
                
                if isinstance(pageItem, Page):  # Bump page points inwards so we snap to margin, not outside edge
                    itemDict[pageItem][0] += margin
                    itemDict[pageItem][1] += margin
                    itemDict[pageItem][2] -= margin
                    itemDict[pageItem][3] -= margin

        if not itemDict:
            return  # Nothing to snap to
        
        # Get top-left & bottom-right corners of target item
        tl, br = item.getCorners()
        
        # Placeholders for current nearest corner & item
        nearestX = dx = x = nearestY = dy = y = 100
        newXItem = newYItem = None
        
        def snapEdge(targetEdge, itemEdge, nearest, dt, t, currentItem, newItem):
            i = targetEdge - itemEdge
            if abs(i) < nearest:
                return abs(i), i, targetEdge, newItem
            return nearest, dt, t, currentItem
            
        def snapX(targetEdge, itemEdge):
            return snapEdge(targetEdge, itemEdge, nearestX, dx, x, newXItem, pageItem)

        def snapY(targetEdge, itemEdge):
            return snapEdge(targetEdge, itemEdge, nearestY, dy, y, newYItem, pageItem)

        for pageItem, pts in itemDict.items():

            if isinstance(pageItem, Guide):
                left, top = pts
                right, bottom = pts
            else:
                left, top, right, bottom = pts

            nearestX, dx, x, newXItem = snapX(left, tl.x())   # Compare left edges
            nearestX, dx, x, newXItem = snapX(right, br.x())  # Compare right edges
                
            nearestY, dy, y, newYItem = snapY(top, tl.y())     # Compare top edges
            nearestY, dy, y, newYItem = snapY(bottom, br.y())  # Compare bottom edges
            
            if not isinstance(pageItem, Page):
                
                # Check if two items line up horizontally / vertically.  Snap with margin on opposite sides if so
                if (top < tl.y() and bottom > br.y()) or (top > tl.y() and bottom < br.y()):
                    nearestX, dx, x, newXItem = snapX(right + margin, tl.x())  # Snap item's left edge to right w. margin
                    nearestX, dx, x, newXItem = snapX(left - margin, br.x())   # Snap item's right edge to left

                if (left < tl.x() and right > br.x()) or (left > tl.x() and right < br.x()):
                    nearestY, dy, y, newYItem = snapY(bottom + margin, tl.y()) # Snap item's bottom edge to top w. margin
                    nearestY, dy, y, newYItem = snapY(top - margin, br.y())    # Snap item's top edge to bottom 

        # Snap item into position
        if nearestX < snapDistance:
            item.moveBy(dx, 0)
        if nearestY < snapDistance:
            item.moveBy(0, dy)

        tl, br = item.getCorners() # Get top-left & bottom-right corners of newly positioned item
    
        # Position a little snap guide line between item & snapped-to item
        if nearestX < snapDistance:
            if isinstance(newXItem, Guide):
                top, bottom = tl.y() + 10, br.y() - 10
            else:
                left, top, right, bottom = itemDict[newXItem]  # Look up item points to snap to
                
            self.xSnapLine.setLine(x, min(top, tl.y()), x, max((bottom, br.y()))) # Position  snap guide line
            self.xSnapLine.show()

        if nearestY < snapDistance:
            if isinstance(newYItem, Guide):
                left, right = tl.x() + 10, br.x() - 10
            else:
                left, top, right, bottom = itemDict[newYItem]  # Look up item points to snap to
                
            self.ySnapLine.setLine(min(left, tl.x()), y, max((right, br.x())), y) # Position  snap guide line
            self.ySnapLine.show()
    
    def mouseReleaseEvent(self, event):

        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)

        QGraphicsScene.mouseReleaseEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

        self.emit(SIGNAL("sceneClick"))
        
    def mousePressEvent(self, event):
        
        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)

        QGraphicsScene.mousePressEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

    def contextMenuEvent(self, event):

        # We can't use the default handler at all because it calls the menu of the 
        # item that was *right-clicked on*, not the menu of the selected items.
        # So check if clicked item is selected.
        clickedItem = self.itemAt(event.scenePos())
        if clickedItem and clickedItem.isSelected():
            return clickedItem.contextMenuEvent(event)
        
        selList = self.selectedItems()
        if selList:
            return selList[-1].contextMenuEvent(event)
        event.ignore()

    def keyPressEvent(self, event):
        if not self.selectedItems():
            event.ignore()
        else:
            event.accept()
        
    def keyReleaseEvent(self, event):
        if not self.pages:
            return  # No pages = nothing to do here

        for item in self.selectedItems():
            if isinstance(item, Part):
                item.keyReleaseEvent(event)
                return

        key = event.key()
        offset = 1
        x = y = 0

        if event.modifiers() & Qt.ShiftModifier:
            offset = 20 if event.modifiers() & Qt.ControlModifier else 5

        if key == Qt.Key_PageUp:
            return self.pageUp()
        if key == Qt.Key_PageDown:
            return self.pageDown()
        if key == Qt.Key_Home:
            return self.selectFirstPage()
        if key == Qt.Key_End:
            return self.selectLastPage()

        if key == Qt.Key_Left:
            x = -offset
        elif key == Qt.Key_Right:
            x = offset
        elif key == Qt.Key_Up:
            y = -offset
        elif key == Qt.Key_Down:
            y = offset
        else:
            event.ignore()  # We do not handle this key stroke here - pass it on and return
            return

        movedItems = []
        for item in self.selectedItems():
            if isinstance(item, Page):
                continue  # Pages cannot be moved

            item.oldPos = item.pos()
            item.moveBy(x, y)
            movedItems.append(item)

        if movedItems:
            self.emit(SIGNAL("itemsMoved"), movedItems)
        event.accept()

class Guide(QGraphicsLineItem):
    
    extends = 500
    
    def __init__(self, orientation, sceneRect):
        QGraphicsLineItem.__init__(self)
        
        self.orientation = orientation
        self.setFlags(AllFlags)
        self.setPen(QPen(QColor(0, 0, 255, 128)))  # Blue 1/2 transparent
        #self.setPen(QPen(QBrush(QColor(0, 0, 255, 128)), 1.5))  # Blue 1/2 transparent, 1.5 thick
        self.setZValue(10000)  # Put on top of everything else
        
        length = sceneRect.width() if orientation == Layout.Horizontal else sceneRect.height()
        pw, ph = Page.PageSize.width(), Page.PageSize.height()
        if orientation == Layout.Horizontal:
            self.setCursor(Qt.SplitVCursor)
            self.setLine(-self.extends, ph / 2.0, length + self.extends, ph / 2.0)
        else:
            self.setCursor(Qt.SplitHCursor)
            self.setLine(pw / 2.0, -self.extends, pw / 2.0, length + self.extends)

    def setLength(self, length):
        line = self.line()
        line.setLength(length + self.extends + self.extends)
        self.setLine(line)

    def mouseMoveEvent(self, event):
        if self.orientation == Layout.Horizontal:
            x = self.pos().x()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(x, self.pos().y())
        else:
            y = self.pos().y()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(self.pos().x(), y)

class LicGraphicsView(QGraphicsView):
    def __init__(self, parent):
        QGraphicsView.__init__(self,  parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(Qt.gray))

    def scaleView(self, scaleFactor):
        
        if scaleFactor == 1.0:
            self.scene().scaleFactor = scaleFactor
            self.resetTransform()
        else:
            factor = self.matrix().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()
    
            if factor >= 0.15 and factor <= 5:
                self.scene().scaleFactor = factor
                self.scale(scaleFactor, scaleFactor)

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.connect(self, SIGNAL("pressed(QModelIndex)"), self.clicked)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setAutoExpandDelay(400)
        self.scene = None
        self.expandedDepth = 0

    def walkTreeModel(self, cmp, action):
        
        model = self.model()
        
        def traverse(index):
            
            if index.isValid() and cmp(index):
                action(index)
                 
            for row in range(model.rowCount(index)):
                if not index.isValid() and row == 0:
                    continue  # Special case: skip the template page
                traverse(model.index(row, 0, index))
        
        traverse(QModelIndex())

    def hideRowInstance(self, instanceType, hide):
        # instanceType can be either concrete type like PLI or itemClassString
        # like "Page Number" (for specific QGraphicsSimpleTextItems) 

        def cmp(index):
            ptr = index.internalPointer()
            if isinstance(instanceType, str):
                return ptr.itemClassName == instanceType
            return isinstance(ptr, instanceType)

        action = lambda index: self.setRowHidden(index.row(), index.parent(), hide)
        self.walkTreeModel(cmp, action)

    def collapseAll(self):
        QTreeView.collapseAll(self)
        self.expandedDepth = 0

    def expandOneLevel(self):
        self.expandToDepth(self.expandedDepth)
        self.expandedDepth += 1

    def keyPressEvent(self, event):
        
        key = event.key()
        if key == Qt.Key_PageUp:
            self.scene.pageUp()
        elif key == Qt.Key_PageDown:
            self.scene.pageDown()
        else:
            QTreeView.keyPressEvent(self, event)
            self.clicked(self.currentIndex())
    
    def updateTreeSelection(self):
        """ This is called whenever the graphics scene is clicked """
        
        # Deselect everything in the tree
        model = self.model()
        selection = self.selectionModel()
        selection.clear()

        # Select everything in the tree that's currently selected in the graphics view
        for item in self.scene.selectedItems():
            if not hasattr(item, "row"):  # Ignore stuff like guides & snap lines
                continue
            index = model.createIndex(item.row(), 0, item)
            if index:
                self.setCurrentIndex(index)
                selection.select(index, QItemSelectionModel.Select)
                self.scrollTo(index)

    def clicked(self, index = None):

        if QApplication.mouseButtons() == Qt.RightButton:
            return  # Ignore right clicks - they're passed on to selected item for their context menu
        
        selList = self.selectionModel().selectedIndexes()
        internalPtr = index.internalPointer()

        # Clear any existing selection from the graphics view
        self.scene.clearSelection()

        if not selList:
            return  # Nothing selected = nothing to do here

        # Find the selected item's parent page, then flip to that page
        if isinstance(internalPtr, Submodel):
            self.scene.selectPage(internalPtr.pages[0].number)
        else:
            page = internalPtr.getPage()
            self.scene.selectPage(page._number)

        # Finally, select the things we actually clicked on
        partList = []
        for index in selList:
            item = index.internalPointer()
            if isinstance(item, Part):
                partList.append(item)
            else:
                item.setSelected(True)
                
        # Optimization: don't just select each parts, because selecting a part forces its CSI to redraw.
        # Instead, only redraw the CSI once, on the last part update
        if partList:
            for part in partList[:-1]:
                part.setSelected(True, False)
            partList[-1].setSelected(True, True)

    def contextMenuEvent(self, event):
        # Pass right clicks on to the item right-clicked on
        selList = self.selectionModel().selectedIndexes()
        if not selList:
            event.ignore()
            return
        
        # 'Convert' QContextMenuEvent to QGraphicsSceneContextMenuEvent
        event.screenPos = event.globalPos
        item = selList[-1].internalPointer()
        return item.contextMenuEvent(event)

class LicTreeWidget(QWidget):
    """
    Combines a LicTreeView (itself a full widget) and a toolbar with a few buttons to control the tree layout.
    """
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
        self.tree = LicTreeView(self)
        self.hiddenRowActions = []
        
        self.treeToolBar = QToolBar("Tree Toolbar", self)
        self.treeToolBar.setIconSize(QSize(15, 15))
        self.treeToolBar.setStyleSheet("QToolBar { border: 0px; }")
        self.treeToolBar.addAction(QIcon(":/expand"), "Expand", self.tree.expandOneLevel)
        self.treeToolBar.addAction(QIcon(":/collapse"), "Collapse", self.tree.collapseAll)

        viewToolButton = QToolButton(self.treeToolBar)
        viewToolButton.setIcon(QIcon(":/down_arrow"))
        viewToolButton.setStyleSheet("QToolButton::menu-indicator { image: url(:/blank) }")
        
        viewMenu = QMenu(viewToolButton)

        def addViewAction(title, slot, checked = True):
            action = QAction(title, viewMenu)
            action.setCheckable(True)
            action.setChecked(checked)
            action.connect(action, SIGNAL("toggled(bool)"), slot)
            action.action = slot
            viewMenu.addAction(action)
            return action

        #viewMenu.addAction("Show All", self.tree.showAll)
        addViewAction("Show Page | Step | Part", self.setShowPageStepPart, False)
        viewMenu.addSeparator()
        addViewAction("Group Parts by type", self.setShowCSIPartGroupings)
        viewMenu.addSeparator()

        self.hiddenRowActions.append(addViewAction("Show Page Number", lambda show: self.tree.hideRowInstance("Page Number", not show)))
        self.hiddenRowActions.append(addViewAction("Show Step Number", lambda show: self.tree.hideRowInstance("Step Number", not show)))
        
        self.csiCheckAction = addViewAction("Show CSI", self.setShowCSI)  # Special case - stuff inside CSI needs to move into Step if CSI hidden
        
        self.hiddenRowActions.append(addViewAction("Show PLI", lambda show: self.tree.hideRowInstance(PLI, not show)))
        self.hiddenRowActions.append(addViewAction("Show PLI Items", lambda show: self.tree.hideRowInstance(PLIItem, not show)))
        self.hiddenRowActions.append(addViewAction("Show PLI Item Qty", lambda show: self.tree.hideRowInstance("PLIItem Quantity", not show)))
        self.hiddenRowActions.append(addViewAction("Show Callouts", lambda show: self.tree.hideRowInstance(Callout, not show)))
        self.hiddenRowActions.append(addViewAction("Show Submodel Previews", lambda show: self.tree.hideRowInstance(SubmodelPreview, not show)))
        
        viewToolButton.setMenu(viewMenu)
        viewToolButton.setPopupMode(QToolButton.InstantPopup)
        viewToolButton.setToolTip("Show / Hide")
        viewToolButton.setFocusPolicy(Qt.NoFocus)
        self.treeToolBar.addWidget(viewToolButton)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.treeToolBar, 0, Qt.AlignRight)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def configureTree(self, scene, treeModel, selectionModel):
        self.tree.scene = scene
        self.tree.setModel(treeModel)
        self.tree.setSelectionModel(selectionModel)

    def setShowPageStepPart(self, show):
        self.csiCheckAction.setChecked(not show)
        for action in self.hiddenRowActions:
            action.setChecked(not show)
    
    def setShowCSIPartGroupings(self, show):
        model = self.tree.model()
        model.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicTreeModel.CSITreeManager.showPartGroupings = show
        
        # Need to reset all cached Part data strings 
        cmp = lambda index: isinstance(index.internalPointer(), Part)
        action = lambda index: index.internalPointer().resetDataString()
        self.tree.walkTreeModel(cmp, action)
        
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def setShowCSI(self, show):
        model = self.tree.model()
        model.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicTreeModel.StepTreeManager.showCSI = show
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def resetHiddenRows(self, ):
        for action in self.hiddenRowActions:
            action.action(action.isChecked())

class LicWindow(QMainWindow):

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        
        self.loadSettings()
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), lambda isClean: self.setWindowModified(not isClean))

        self.glWidget = QGLWidget(GLHelpers.getGLFormat(), self)
        self.treeWidget = LicTreeWidget(self)

        statusBar = self.statusBar()
        self.scene = LicGraphicsScene(self)
        self.scene.undoStack = self.undoStack  # Make undo stack easy to find for everything
        self.copySettingsToScene()

        self.graphicsView = LicGraphicsView(self)
        self.graphicsView.setViewport(self.glWidget)
        self.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        
        # Connect the items moved signal to a push command on undo stack
        self.connect(self.scene, SIGNAL("itemsMoved"), lambda x: self.undoStack.push(LicUndoActions.MoveCommand(x)))

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeWidget)
        self.mainSplitter.addWidget(self.graphicsView)
        self.mainSplitter.restoreState(self.splitterState)
        self.setCentralWidget(self.mainSplitter)

        self.initMenu()
        self.initToolBars()

        self.instructions = Instructions(self, self.scene, self.glWidget)
        self.treeModel = LicTreeModel.LicTreeModel(self.treeWidget.tree)
        #self.modelTest = ModelTest(self.treeModel, self)
        
        self.selectionModel = QItemSelectionModel(self.treeModel)  # MUST keep own reference to selection model here
        self.treeWidget.configureTree(self.scene, self.treeModel, self.selectionModel)
        self.treeWidget.tree.connect(self.scene, SIGNAL("sceneClick"), self.treeWidget.tree.updateTreeSelection)
        self.scene.connect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChanged)

        # Allow the graphics scene and instructions to emit the layoutAboutToBeChanged and layoutChanged 
        # signals, for easy notification of layout changes everywhere
        self.connect(self.scene, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.scene, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))
        self.connect(self.instructions, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.instructions, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))

        # AbstractItemModels keep a list of persistent indices around, which we need to update after layout change
        self.connect(self.treeModel, SIGNAL("layoutChanged()"), self.treeModel.updatePersistentIndices)

        # Need to notify the Model when a particular index was deleted
        self.treeModel.connect(self.scene, SIGNAL("itemDeleted"), self.treeModel.deletePersistentItem)
            
        self.filename = ""   # This will trigger the __setFilename method below

    def getSettingsFile(self):
        iniFile = os.path.join(os.path.dirname(sys.argv[0]), 'Lic.ini')
        return QSettings(QString(iniFile), QSettings.IniFormat)
        
    def loadSettings(self):
        settings = self.getSettingsFile()
        self.recentFiles = settings.value("RecentFiles").toStringList()
        self.restoreGeometry(settings.value("Geometry").toByteArray())
        self.restoreState(settings.value("MainWindow/State").toByteArray())
        self.splitterState = settings.value("SplitterSizes").toByteArray()
        self.pagesToDisplay = settings.value("PageView").toInt()[0]
        self.snapToGuides = settings.value("SnapToGuides").toBool()
        self.snapToItems = settings.value("SnapToItems").toBool()
    
    def saveSettings(self):
        settings = self.getSettingsFile()
        recentFiles = QVariant(self.recentFiles) if self.recentFiles else QVariant()
        settings.setValue("RecentFiles", recentFiles)
        settings.setValue("Geometry", QVariant(self.saveGeometry()))
        settings.setValue("MainWindow/State", QVariant(self.saveState()))
        settings.setValue("SplitterSizes", QVariant(self.mainSplitter.saveState()))
        settings.setValue("PageView", QVariant(str(self.scene.pagesToDisplay)))
        settings.setValue("SnapToGuides", QVariant(str(self.scene.snapToGuides)))
        settings.setValue("SnapToItems", QVariant(str(self.scene.snapToItems)))
        
    def copySettingsToScene(self):
        self.scene.setPagesToDisplay(self.pagesToDisplay)
        self.scene.snapToGuides = self.snapToGuides
        self.scene.snapToItems = self.snapToItems
        
    def __getFilename(self):
        return self.__filename
    
    def __setFilename(self, filename):
        self.__filename = filename
        
        if filename:
            config.config = self.initConfig()
            self.setWindowTitle("Lic %s - %s [*]" % (__version__, os.path.basename(filename)))
            self.statusBar().showMessage("Instruction book loaded: " + filename)
            enabled = True
        else:
            config.config = {}
            self.undoStack.clear()
            self.setWindowTitle("Lic %s [*]" % __version__)
            self.statusBar().showMessage("")
            enabled = False

        self.undoStack.setClean()
        self.setWindowModified(False)
        self.enableMenus(enabled)

    filename = property(fget = __getFilename, fset = __setFilename)
            
    def initConfig(self, filename = ""):
        """ 
        Create cache folders for temp dats, povs & pngs, if necessary.
        Cache folders are stored as 'LicPath/cache/modelName/[DATs|POVs|PNGs]'
        """
        
        config = {}
        cachePath = os.path.join(os.getcwd(), 'cache')        
        if not os.path.isdir(cachePath):
            os.mkdir(cachePath)
            
        fn = filename if self.filename == "" else self.filename
        modelPath = os.path.join(cachePath, os.path.basename(fn))
        if not os.path.isdir(modelPath):
            os.mkdir(modelPath)
        
        config['datPath'] = os.path.join(modelPath, 'DATs')
        if not os.path.isdir(config['datPath']):
            os.mkdir(config['datPath'])   # Create DAT directory if needed

        config['povPath'] = os.path.join(modelPath, 'POVs')
        if not os.path.isdir(config['povPath']):
            os.mkdir(config['povPath'])   # Create POV directory if needed

        config['pngPath'] = os.path.join(modelPath, 'PNGs')
        if not os.path.isdir(config['pngPath']):
            os.mkdir(config['pngPath'])   # Create PNG directory if needed

        config['imgPath'] = os.path.join(modelPath, 'Final_Images')
        if not os.path.isdir(config['imgPath']):
            os.mkdir(config['imgPath'])   # Create final image directory if needed

        config['GLImgPath'] = os.path.join(modelPath, 'GL_Images')
        if not os.path.isdir(config['GLImgPath']):
            os.mkdir(config['GLImgPath'])   # Create directory for GL renderings if needed

        config['PDFPath'] = os.path.join(modelPath, 'PDFs')
        if not os.path.isdir(config['PDFPath']):
            os.mkdir(config['PDFPath'])   # Create directory for GL renderings if needed

        return config

    def initToolBars(self):
        self.toolBar = None
    
    def initMenu(self):
        
        menu = self.menuBar()
        
        # File Menu
        self.fileMenu = menu.addMenu("&File")
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"), self.updateFileMenu)

        fileOpenAction = self.createMenuAction("&Open...", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")

        self.fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing LDraw Model into a new Instruction book")

        self.fileSaveTemplateAction = self.createMenuAction("Save Template", self.fileSaveTemplate, None, "Save only the Template")
        self.fileSaveTemplateAsAction = self.createMenuAction("Save Template As...", self.fileSaveTemplateAs, None, "Save only the Template using a new filename")
        self.fileLoadTemplateAction = self.createMenuAction("Load Template", self.fileLoadTemplate, None, "Discard the current Template and apply a new one")
        fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")

        self.fileMenuActions = (fileOpenAction, self.fileCloseAction, None, 
                                self.fileSaveAction, self.fileSaveAsAction, fileImportAction, None, 
                                self.fileSaveTemplateAction, self.fileSaveTemplateAsAction, self.fileLoadTemplateAction, None,
                                fileExitAction)
        
        # Edit Menu - undo / redo is generated dynamically in updateEditMenu()
        self.editMenu = menu.addMenu("&Edit")
        self.connect(self.editMenu, SIGNAL("aboutToShow()"), self.updateEditMenu)

        self.undoAction = self.createMenuAction("&Undo", None, "Ctrl+Z", "Undo last action")
        self.undoAction.connect(self.undoAction, SIGNAL("triggered()"), self.undoStack, SLOT("undo()"))
        self.undoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canUndoChanged(bool)"), self.undoAction, SLOT("setEnabled(bool)"))
        
        self.redoAction = self.createMenuAction("&Redo", None, "Ctrl+Y", "Redo the last undone action")
        self.redoAction.connect(self.redoAction, SIGNAL("triggered()"), self.undoStack, SLOT("redo()"))
        self.redoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canRedoChanged(bool)"), self.redoAction, SLOT("setEnabled(bool)"))
        
        editActions = (self.undoAction, self.redoAction, None)
        self.addActions(self.editMenu, editActions)

        # Snap menu (inside Edit Menu): Snap -> Snap to Guides & Snap to Items
        guideSnapAction = self.createMenuAction("Guides", self.setSnapToGuides, None, "Snap To Guides", "toggled(bool)")
        guideSnapAction.setCheckable(True)
        guideSnapAction.setChecked(self.scene.snapToGuides)
        
        itemSnapAction = self.createMenuAction("Items", self.setSnapToItems, None, "Snap To Items", "toggled(bool)")
        itemSnapAction.setCheckable(True)
        itemSnapAction.setChecked(self.scene.snapToItems)
        
        snapMenu = self.editMenu.addMenu("Snap To")
        snapMenu.addAction(guideSnapAction)
        snapMenu.addAction(itemSnapAction)

        # View Menu
        self.viewMenu = menu.addMenu("&View")
        addHGuide = self.createMenuAction("Add Horizontal Guide", lambda: self.scene.addNewGuide(Layout.Horizontal), None, "Add Guide")
        addVGuide = self.createMenuAction("Add Vertical Guide", lambda: self.scene.addNewGuide(Layout.Vertical), None, "Add Guide")
        removeGuides = self.createMenuAction("Remove Guides", self.scene.removeAllGuides, None, "Add Guide")

        zoom100 = self.createMenuAction("Zoom &100%", lambda: self.zoom(1.0), None, "Zoom 100%")
        zoomIn = self.createMenuAction("Zoom &In", lambda: self.zoom(1.2), None, "Zoom In")
        zoomOut = self.createMenuAction("Zoom &Out", lambda: self.zoom(1.0 / 1.2), None, "Zoom Out")

        onePage = self.createMenuAction("Show One Page", self.scene.showOnePage, None, "Show One Page")
        twoPages = self.createMenuAction("Show Two Pages", self.scene.showTwoPages, None, "Show Two Pages")
        continuous = self.createMenuAction("Continuous", self.scene.continuous, None, "Continuous")
        continuousFacing = self.createMenuAction("Continuous Facing", self.scene.continuousFacing, None, "Continuous Facing")
        
        viewActions = (addHGuide, addVGuide, removeGuides, None, zoom100, zoomIn, zoomOut, None, onePage, twoPages, continuous, continuousFacing)
        self.addActions(self.viewMenu, viewActions)

        # Page Menu
        self.pageMenu = menu.addMenu("&Page")

        pageSizeAction = self.createMenuAction("Page Size...", self.changePageSizeAction, None, "Change the overall size of all Pages in this Instruction book")       
        self.addActions(self.pageMenu, (pageSizeAction,))
        
        # Export Menu
        self.exportMenu = menu.addMenu("E&xport")
        self.exportToImagesAction = self.createMenuAction("&Generate Final Images", self.exportImages, None, "Generate final images of each page in this Instruction book")
        self.exportToPDFAction = self.createMenuAction("Generate &PDF", self.exportToPDF, None, "Create a PDF from this instruction book")
        self.exportToPOVAction = self.createMenuAction("Generate Images with Pov-Ray", self.exportToPOV, None, "Use Pov-Ray to generate final, ray-traced images of each page in this Instruction book")
        self.addActions(self.exportMenu, (self.exportToImagesAction, self.exportToPDFAction, self.exportToPOVAction))

    def changePageSizeAction(self):
        dialog = LicDialogs.PageSizeDlg(self, Page.PageSize, Page.Resolution)
        if dialog.exec_():
            newPageSize = dialog.getPageSize()
            newRes = dialog.getResolution()
            doRescale = dialog.getRescalePageItems()
            self.undoStack.beginMacro("Page Resize")
            self.undoStack.push(LicUndoActions.ResizePageCommand(self, Page.PageSize, newPageSize, Page.Resolution, newRes, doRescale))
            self.undoStack.endMacro()

    def setPageSize(self, newPageSize, newResolution, doRescale, newScale):
        
        if (newPageSize.width() == Page.PageSize.width() and newPageSize.height() == Page.PageSize.height()) and (newResolution != Page.Resolution):
            return
        
        if doRescale:
            self.templatePage.scaleAllItems(newScale)
        
        Page.PageSize = newPageSize
        Page.Resolution = newResolution
        self.templatePage.setRect(0, 0, newPageSize.width(), newPageSize.height())
        self.templatePage.initLayout()
        self.instructions.setPageSize(Page.PageSize)
        self.scene.refreshView()

    def zoom(self, factor):
        self.graphicsView.scaleView(factor)
        
    def setSnapToGuides(self, snap):
        self.snapToGuides = self.scene.snapToGuides = snap

    def setSnapToItems(self, snap):
        self.snapToItems = self.scene.snapToItems = snap
        
    def updateFileMenu(self):
        self.fileMenu.clear()
        self.addActions(self.fileMenu, self.fileMenuActions[:-1])  # Don't add last Exit yet
        
        recentFiles = []
        for filename in self.recentFiles:
            if filename != QString(self.filename) and QFile.exists(filename):
                recentFiles.append(filename)
                
        if recentFiles:
            self.fileMenu.addSeparator()
            
            for i, filename in enumerate(recentFiles):
                action = QAction("&%d %s" % (i+1, QFileInfo(filename).fileName()), self)
                action.setData(QVariant(filename))
                action.setStatusTip(filename)
                self.connect(action, SIGNAL("triggered()"), self.openRecentFile)
                self.fileMenu.addAction(action)
            
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileMenuActions[-1])

    def openRecentFile(self):
        action = self.sender()
        filename = unicode(action.data().toString())
        self.fileOpen(filename)

    def updateEditMenu(self):
        self.undoAction.setText("&Undo %s " % self.undoStack.undoText())
        self.redoAction.setText("&Redo %s " % self.undoStack.redoText())

    def addRecentFile(self, filename):
        if self.recentFiles.contains(filename):
            self.recentFiles.move(self.recentFiles.indexOf(filename), 0)
        else:
            self.recentFiles.prepend(QString(filename))
            while self.recentFiles.count() > 9:
                self.recentFiles.takeLast()
    
    def addActions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)
    
    def createMenuAction(self, text, slot = None, shortcut = None, tip = None, signal = "triggered()"):
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        return action

    def closeEvent(self, event):
        if self.offerSave():
            self.saveSettings()
            
            # Need to explicitly disconnect this signal, because the scene emits a selectionChanged right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChanged)
            self.glWidget.doneCurrent()  # Avoid a crash when exiting
            event.accept()
        else:
            event.ignore()

    def fileClose(self, offerSave = True):
        if offerSave and not self.offerSave():
            return
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.instructions.clear()
        self.treeModel.reset()
        self.treeModel.root = None
        self.scene.clear()
        self.filename = ""
        self.scene.emit(SIGNAL("layoutChanged()"))

    def offerSave(self):
        """ 
        Returns True if we should proceed with whatever operation
        was interrupted by this request.  False means cancel.
        """
        if not self.isWindowModified():
            return True
        reply = QMessageBox.question(self, "Lic - Unsaved Changes", "Save unsaved changes?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            return self.fileSave()
        return reply == QMessageBox.No

    def fileImport(self):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        formats = ["*.mpd", "*.ldr", "*.dat"]
        filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Import LDraw Model", dir, "LDraw Models (%s)" % " ".join(formats)))
        if filename:
            QTimer.singleShot(50, lambda: self.importLDrawModelTimerAction(filename))

    def importLDrawModelTimerAction(self, filename):
        self.fileClose()
        self.importLDrawModel(filename)
        self.statusBar().showMessage("LDraw Model imported: " + filename)
        self.scene.selectPage(1)
        self.copySettingsToScene()

    def loadLicFile(self, filename):
        
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicBinaryReader.loadLicFile(filename, self.instructions)
        self.treeModel.root = self.instructions.mainModel
        self.scene.emit(SIGNAL("layoutChanged()"))
        
        self.filename = filename
        self.addRecentFile(filename)
        self.scene.selectPage(1)
        self.copySettingsToScene()
    
    def importLDrawModel(self, filename):

        progress = QProgressDialog(self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("Importing " + os.path.splitext(os.path.basename(filename))[0])
        progress.setMinimumDuration(0)
        progress.setCancelButtonText("Cancel")
        progress.setRange(0, 10)
        progress.setLabelText("Reading LDraw File")
        progress.setValue(1)  # Force dialog to show up right away
        
        loader = self.instructions.importLDrawModel(filename)
        stopValue, title = loader.next()  # First value yielded after load is # of progress steps
        progress.setMaximum(stopValue)
        
        for step, label in loader:
            progress.setLabelText(label)
            progress.setValue(step)
            
            if progress.wasCanceled():
                loader.close()
                self.fileClose()
                return

        progress.setValue(progress.maximum())
        
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.treeModel.root = self.instructions.mainModel

        self.templatePage = LicBinaryReader.loadLicTemplate(r"C:\lic\dynamic_template.lit", self.instructions)
        #self.templatePage = LicTemplate.TemplatePage(self.instructions.mainModel, self.instructions)
        #self.templatePage.createBlankTemplate(self.glWidget)
        
        self.instructions.setTemplate(self.templatePage)
        self.instructions.mainModel.partListPages = LicPartListPage.createPartListPages(self.instructions)
        self.templatePage.applyFullTemplate(False)
        
        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(1)

        config.config = self.initConfig(filename)
        self.statusBar().showMessage("Instruction book loaded")
        self.setWindowModified(True)
        self.enableMenus(True)

    def enableMenus(self, enabled):
        self.fileCloseAction.setEnabled(enabled)
        self.fileSaveAction.setEnabled(enabled)
        self.fileSaveAsAction.setEnabled(enabled)
        self.fileSaveTemplateAction.setEnabled(enabled)
        self.fileSaveTemplateAsAction.setEnabled(enabled)
        self.fileLoadTemplateAction.setEnabled(enabled)
        self.editMenu.setEnabled(enabled)
        self.pageMenu.setEnabled(enabled)
        self.viewMenu.setEnabled(enabled)
        self.exportMenu.setEnabled(enabled)
        self.treeWidget.treeToolBar.setEnabled(enabled)
        
    def fileSaveAs(self):
        if self.filename:
            f = self.filename
        else:
            f = self.instructions.getModelName()
            f = f.split('.')[0] + '.lic'
            
        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe File As", f, "Lic Instruction Book files (*.lic)"))
        if filename:
            self.filename = filename
            self.instructions.filename = filename
            return self.fileSave()
        return False

    def fileSave(self):
        if self.filename == "":
            return self.fileSaveAs()
        try:
            LicBinaryWriter.saveLicFile(self.filename, self.instructions, self.templatePage)
            self.undoStack.setClean()
            self.addRecentFile(self.filename)
            self.statusBar().showMessage("Saved to: " + self.filename)
            return True
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (self.filename, e))
        return False

    def fileSaveTemplate(self):
        template = self.templatePage
        try:
            LicBinaryWriter.saveLicTemplate(template)
            self.statusBar().showMessage("Saved Template to: " + template.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (template.filename, e))
    
    def fileSaveTemplateAs(self):
        template = self.templatePage
        f = template.filename if template.filename else "template.lic"

        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe Template As", f, "Lic Template files (*.lit)"))
        if filename:
            template.filename = filename
            self.fileSaveTemplateAction.setEnabled(True)
            return self.fileSaveTemplate()
    
    def fileLoadTemplate(self):
        templateName = self.templatePage.filename
        dir = os.path.dirname(templateName) if templateName is not None else "."
        newFilename = unicode(QFileDialog.getOpenFileName(self, "Lic - Load Template", dir, "Lic Template files (*.lit)"))
        if newFilename and newFilename != templateName:
            try:
                newTemplate = LicBinaryReader.loadLicTemplate(newFilename, self.instructions)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Load Template Error", "Failed to open %s: %s" % (newFilename, e))
            else:
                self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
                self.templatePage = newTemplate
                self.templatePage.applyFullTemplate()
                self.scene.emit(SIGNAL("layoutChanged()"))
                self.setWindowModified(True)
    
    def fileOpen(self, filename = None):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        
        if filename is None:
            filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Open Instruction Book", dir, "Lic Instruction Book files (*.lic)"))
            
        if filename and filename != self.filename:
            self.fileClose(False)
            try:
                self.loadLicFile(filename)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Open Error", "Failed to open %s: %s" % (filename, e))
                self.fileClose()

    def exportImages(self):
        self.instructions.exportImages()
        self.glWidget.makeCurrent()
        print "\nExported images to: " + config.config['imgPath']

    def exportToPDF(self):
        filename = self.instructions.exportToPDF()
        self.glWidget.makeCurrent()
        print "\nExported PDF to: " + filename
                 
    def exportToPOV(self):
        print "THIS IS CURRENTLY NOT WORKING - Rendered item Rotation is way out"
        self.instructions.exportToPOV()
        print "\nExport complete"

def main():
    
    #f = QGLFormat.defaultFormat()
    #f.setSampleBuffers(True)
    #QGLFormat.setDefaultFormat(f)
    
    app = QApplication(sys.argv)
    app.setOrganizationName("BugEyedMonkeys Inc.")
    app.setOrganizationDomain("bugeyedmonkeys.com")
    app.setApplicationName("Lic")
    window = LicWindow()

    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    window.show()
    filename = ""
    #filename = unicode("C:/lic/tardis.mpd")
    #filename = unicode("C:/lic/tardis.lic")
    #filename = unicode("C:/lic/viper_white.lic")
    #filename = unicode("C:/lic/viper_short.lic")
    #filename = unicode("C:/lic/viper_short.mpd")
    #filename = unicode("C:/lic/viper.mpd")
    #filename = unicode("C:/lic/Blaster.mpd")
    #filename = unicode("C:/lic/2x4.lic")
    #filename = unicode("C:/lic/6x10.lic")
    #filename = unicode("C:/lic/6x10.dat")
    #filename = unicode("C:/lic/template.dat")
    #filename = unicode("C:/lic/pins.ldr")
    #filename = unicode("C:/lic/stack.lic")
    #filename = unicode("C:/lic/1x1x2.dat")
    #filename = unicode("C:/lic/headlight_simple.dat")
    #filename = unicode("C:/lic/headlight.dat")
    #filename = unicode("C:/lic/displace.lic")
    #filename = unicode("C:/lic/pyramid.lic")
    #filename = unicode("C:/lic/2_brick_stack.lic")
    #filename = unicode("C:/lic/viper_white.lic")
    #filename = unicode("C:/lic/2bricks.lic")
    #filename = unicode("C:/lic/pyramid_callout.lic")

    if filename:
        QTimer.singleShot(50, lambda: loadFile(window, filename))

    sys.exit(app.exec_())

def loadFile(window, filename):

    if filename[-3:] == 'dat' or filename[-3:] == 'mpd' or filename[-3:] == 'ldr':
        window.importLDrawModelTimerAction(filename)
    elif filename[-3:] == 'lic':
        window.fileOpen(filename)
    else:
        print "Bad file extension: " + filename
        return

    window.scene.selectFirstPage()

def recompileResources():
    import os
    ret = os.spawnl(os.P_WAIT, r"C:\Python25\Lib\site-packages\PyQt4\pyrcc4.exe", "pyrcc4.exe", "-o", r"c:\lic\resources.py", r"c:\lic\resources.qrc")
    print ret
    
if __name__ == '__main__':
    #import cProfile
    #cProfile.run('main()', 'profile_run')
    main()
    #recompileResources()

