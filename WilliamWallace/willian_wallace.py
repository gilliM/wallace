# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WilliamWallace
                                 A QGIS plugin
 This plugin do a supervised classification
                              -------------------
        begin                : 2016-05-17
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Gillian
        email                : gillian.milani@geo.uzh.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from PyQt4.QtGui import QAction, QIcon, QMenu, QToolButton, QColor, QKeySequence
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from choose_db_dialog import ChooseDbDialog
from classify_dialog import MyClassifier
import os.path
import qgis
from qgis.core import QgsDataSourceURI, QgsVectorLayer, QgsCategorizedSymbolRendererV2, QgsRendererCategoryV2, QgsSymbolV2, QgsMapLayerRegistry, QgsVectorJoinInfo
s = QSettings()


class WilliamWallace:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'WilliamWallace_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&William Wallace')
        self.join = []


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('WilliamWallace', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.action1 = QAction(QIcon(":/plugins/WilliamWallace/icons/tiger.png"), u"Choose target DB", self.iface.mainWindow())
        self.action2 = QAction(QIcon(":/plugins/WilliamWallace/icons/tiger.png"), u"Apply Symbology", self.iface.mainWindow())
        self.action3 = QAction(QIcon(":/plugins/WilliamWallace/icons/tiger.png"), u"Classify", self.iface.mainWindow())
        self.action3.setShortcut(QKeySequence(Qt.SHIFT + Qt.Key_G))
        self.actions.append(self.action1)
        self.actions.append(self.action2)
        self.actions.append(self.action3)
        self.popupMenu = QMenu(self.iface.mainWindow())
        self.popupMenu.addAction(self.action1)
        self.popupMenu.addAction(self.action2)
        self.popupMenu.addAction(self.action3)
        self.action1.triggered.connect(self.ChooseTargetDB)
        self.action2.triggered.connect(self.applySymbology)
        self.action3.triggered.connect(self.classify)
        self.toolButton = QToolButton()
        self.toolButton.setMenu(self.popupMenu)
        self.toolButton.setDefaultAction(self.action1)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)
        self.toolbar1 = self.iface.addToolBarWidget(self.toolButton)

    def ChooseTargetDB(self):
        dialog = ChooseDbDialog()
        dialog.show()
        ok = dialog.exec_()
        if ok:
            name = dialog.comboBox.currentText()
            if name == '' or name is None:
                return
            s.setValue('WallacePlugins/connectionName', name)
        return

    def applySymbology(self):
        self.getConnection()
        vlayer = qgis.utils.iface.mapCanvas().currentLayer()
        if vlayer == None:
            return

        fields = vlayer.dataProvider().fields()
        classField = None
        for f in fields:
            if f.name() == "classtype":
                classField = 'classtype'
            elif f.name() == "result":
                classField = 'result'
        print classField

        class_loaded = False
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if  layer.name() == "class":
                vlayerClass = layer
                class_loaded = True
        if not class_loaded:
            uriSubClass = QgsDataSourceURI()
            uriSubClass.setConnection(self.serverName, "5432", self.database, self.usr , self.pw)
            uriSubClass.setDataSource("classification", "class", None, "", "id")
            vlayerClass = QgsVectorLayer(uriSubClass.uri(), "class", "postgres")
            QgsMapLayerRegistry.instance().addMapLayer(vlayerClass)

        for field in fields:
            index = vlayer.fieldNameIndex(field.name())
            if field.name() == classField:
                vlayer.editFormConfig().setWidgetType(index, 'ValueRelation')
                vlayer.editFormConfig().setWidgetConfig(index, {'Layer': vlayerClass.id(), 'Key': 'id', 'Value': 'classname'})

        useJoin = True
        if useJoin:
            joinObject = QgsVectorJoinInfo()
            joinObject.joinLayerId = vlayerClass.id()
            joinObject.joinFieldName = 'id'
            joinObject.targetFieldName = classField
            joinObject.memoryCache = True
            vlayer.addJoin(joinObject)
            self.join.append(joinObject)
            categories = []
            iter = vlayerClass.getFeatures()
            for feature in iter:
                classname = feature['classname']
                color = QColor(feature['red'], feature['green'], feature['blue'])
                sym = QgsSymbolV2.defaultSymbol(vlayer.geometryType())
                sym.setColor(QColor(color))
                category = QgsRendererCategoryV2(classname, sym, classname)
                categories.append(category)
            field = "class_classname"
            renderer = QgsCategorizedSymbolRendererV2(field, categories)
            vlayer.setRendererV2(renderer)

        qgis.utils.iface.messageBar().pushMessage("Information", "Editor widget set", level = qgis.gui.QgsMessageBar.INFO, duration = 5)
        qgis.utils.iface.setActiveLayer(vlayer)

    def classify(self):
        dialog = MyClassifier()
        dialog.show()
        ok = dialog.exec_()
        if ok:
            dialog.run()

    def getConnection(self):
        name = s.value('WallacePlugins/connectionName')
        self.serverName = s.value("PostgreSQL/connections/%s/host" % name)
        self.database = s.value("PostgreSQL/connections/%s/database" % name)
        self.port = "5432"
        self.usr = s.value("PostgreSQL/connections/%s/username" % name)
        self.pw = s.value("PostgreSQL/connections/%s/password" % name)
        connectionString = "PG:dbname='%s' host='%s' port='%s' user='%s'password='%s'" % (self.database, self.serverName, self.port, self.usr, self.pw)
        return connectionString

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removeToolBarIcon(self.toolbar1)
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&William Wallace'),
                action)
            self.iface.removeToolBarIcon(action)
