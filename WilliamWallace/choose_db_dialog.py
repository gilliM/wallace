# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WilliamWallaceDialog
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

import os

from PyQt4 import QtGui, uic, QtCore, QtSql
s = QtCore.QSettings()

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'choose_db_dialog_base.ui'))


class ChooseDbDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent = None):
        """Constructor."""
        super(ChooseDbDialog, self).__init__(parent)
        self.setupUi(self)
        listOfConnections = self.getPostgisConnections()
        self.fillComboBox(listOfConnections)
        currentConnection = s.value('WallacePlugins/connectionName')
        if currentConnection is not None:
            index = self.comboBox.findData(currentConnection)
            self.comboBox.setCurrentIndex(index)

    def fillComboBox(self, list):
        self.comboBox.addItem('', None)
        for name in list:
            self.comboBox.addItem(name, name)

    def getPostgisConnections(self):
        keyList = []
        for key in s.allKeys():
            if key.startswith('PostgreSQL/connections'):
                if key.endswith('database'):
                    connectionName = key.split('/')[2]
                    keyList.append(connectionName)
        return keyList
