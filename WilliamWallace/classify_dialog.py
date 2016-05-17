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
from PyQt4.QtCore import pyqtSlot, QFileInfo
from PyQt4.QtGui import QColor
from qgis.core import QgsMapLayerRegistry, \
                        QgsMapLayer, \
                        QGis, \
                        QgsDataSourceURI, \
                        QgsRasterLayer, \
                        QgsVectorLayer, \
                        QgsColorRampShader, \
                        QgsRasterShader, \
                        QgsSingleBandPseudoColorRenderer
import numpy as np
from osgeo import osr, ogr, gdal, gdalnumeric
import copy
from PIL import Image, ImageDraw
from pyplot_widget import pyPlotWidget

from sklearn.ensemble import RandomForestClassifier

from skimage.filters.rank import median
from skimage.morphology import disk

s = QtCore.QSettings()

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'classify_dialog_base.ui'))


class MyClassifier(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent = None):
        """Constructor."""
        super(MyClassifier, self).__init__(parent)
        self.setupUi(self)

        self.path = os.path.dirname(os.path.realpath(__file__))

        layers = QgsMapLayerRegistry.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QGis.Polygon:
               self.trainingComboBox.addItem(layer.name(), layer)
            if layer.type() == QgsMapLayer.RasterLayer:
               self.rasterComboBox.addItem(layer.name(), layer)

        self.outputLineEdit.setText(self.path + '/temp/output_wallace.tiff')

    @pyqtSlot()
    def on_outputToolButton_clicked(self):
        file = str(QtGui.QFileDialog.getSaveFileName(self, "Select File", self.path + '/temp'))
        if file != "":
            self.outputLineEdit.setText(file)
        return None

    def run(self):
        index = self.rasterComboBox.currentIndex()
        rasterLayer = self.rasterComboBox.itemData(index)
        index = self.rasterComboBox.currentIndex()
        trainingLayer = self.trainingComboBox.itemData(index)
        outputFile = self.outputLineEdit.text()

        rasterDataset = gdal.Open(rasterLayer.source())
        geoTransform = rasterDataset.GetGeoTransform()
        projection = rasterDataset.GetProjection()

        raster = gdalnumeric.LoadFile(rasterLayer.source())
        raster = np.array(raster)
        n_b, n_x, n_y = np.shape(raster)

        conn = ogr.Open(self.getConnection())
        trainingOgrLayer = conn.GetLayer(str("vector.training"))

        dic_groundReference = self.getGroundTruth(raster, trainingOgrLayer, geoTransform, n_x, n_y, n_b)

        y = []
        X = np.empty((0, n_b))
        for key, values in dic_groundReference.iteritems():
            X = np.concatenate((X, values), axis = 0)
            y.extend(values.shape[0] * [key])

        mask = np.sum(raster, 0) != 0
        data_list = raster[:, mask].T
        clf = RandomForestClassifier(n_estimators = 100, n_jobs = -1)
        clf.fit(X, y)
        res = clf.predict(data_list)

        raster_result = np.zeros((n_x, n_y))
        raster_result[mask] = res

        if self.checkBox.isChecked():
            # Smooth a bit...
            raster_result = np.reshape(raster_result, (raster_result.shape[0], raster_result.shape[1]))
            raster_result = np.array(raster_result, dtype = np.uint8)
            raster_result = median(raster_result, disk(3))

        raster_result = np.reshape(raster_result, (raster_result.shape[0], raster_result.shape[1], 1))

        self.WriteGeotiffNBand(raster_result, outputFile, gdal.GDT_Byte, geoTransform, projection)
        self.loadToGgis(outputFile)
        if self.checkBox.isChecked():
            self.saveToPostgis(outputFile, 'vector.result')
            self.loatPostgisTableToQgis('vector', 'result')


    def saveToPostgis(self, rasterFile, outputTable):
        ogrds = ogr.Open(self.getConnection())
        raster = gdal.Open(rasterFile)
        projection = raster.GetProjection()
        geoTransform = raster.GetGeoTransform()

        srs = osr.SpatialReference()
        srs.ImportFromWkt(projection)
        outputLayer = ogrds.CreateLayer(str(outputTable), srs, ogr.wkbPolygon, ['OVERWRITE=YES'])
        conn = ogr.Open(self.getConnection())
        lyr = conn.GetLayer('vector.template_result')
        inLayerDefn = lyr.GetLayerDefn()
        for i in range(0, inLayerDefn.GetFieldCount()):
            fieldDefn = inLayerDefn.GetFieldDefn(i)
            outputLayer.CreateField(fieldDefn)
            if fieldDefn.GetName() == 'result':
                field_id = copy.copy(i)
        gdal.Polygonize(raster.GetRasterBand(1), None, outputLayer, field_id, [], callback = None)

        ogrds = None
        outputLayer = None
        raster = None

    def loatPostgisTableToQgis(self, schema, table):
        uriSubClass = QgsDataSourceURI()
        uriSubClass.setConnection(self.serverName, "5432", self.database, self.usr , self.pw)
        uriSubClass.setDataSource(schema, table, "wkb_geometry", "", "id")
        vlayerClass = QgsVectorLayer(uriSubClass.uri(), table, "postgres")
        QgsMapLayerRegistry.instance().addMapLayer(vlayerClass)

    def loadToGgis(self, outputFile):
        fileInfo = QFileInfo(outputFile)
        baseName = fileInfo.baseName()
        rlayer = QgsRasterLayer(outputFile, baseName)

        fcn = QgsColorRampShader()
        fcn.setColorRampType(QgsColorRampShader.INTERPOLATED)

        getColorQuery = QtSql.QSqlQuery(self.db)
        strQuery = """SELECT id, red, green, blue FROM classification.class;"""
        ok = getColorQuery.exec_(strQuery)
        lst = []
        lst.append(QgsColorRampShader.ColorRampItem(0, QColor(0, 0, 0)))
        while getColorQuery.next():
            j = getColorQuery.value(0)
            print j
            red = getColorQuery.value(1)
            green = getColorQuery.value(2)
            blue = getColorQuery.value(3)
            lst.append(QgsColorRampShader.ColorRampItem(j, QColor(red, green, blue)))

        fcn.setColorRampItemList(lst)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fcn)

        renderer = QgsSingleBandPseudoColorRenderer(rlayer.dataProvider(), 1, shader)
        rlayer.setRenderer(renderer)
        QgsMapLayerRegistry.instance().addMapLayer(rlayer)

    def getGroundTruth(self, raster, trainingOgrLayer, geoTransform, n_x, n_y, n_b):
        dic_groundReference = {}
        for i_f, feature in enumerate(trainingOgrLayer):
            c_class = feature.GetField("classtype")
            points = []; pixels = []
            geom = feature.GetGeometryRef()
            pts = geom.GetGeometryRef(0)
            for p in range(pts.GetPointCount()):
              points.append((pts.GetX(p), pts.GetY(p)))
            for p in points:
              pixels.append(self.world2Pixel(geoTransform, p[0], p[1]))
            rasterPoly = Image.new("L", (n_y, n_x), 1)
            rasterize = ImageDraw.Draw(rasterPoly)
            rasterize.polygon(pixels, 0)
            mask_poly = self.imageToArray(rasterPoly)
            # Clip the image using the mask
            clip = gdalnumeric.choose(mask_poly, (raster, 0))
            transp = clip[-1, :, :]
            newGD = []
            """
            cplot = pyPlotWidget()
            fig = cplot.figure
            ax = cplot.figure.add_subplot(111)
            ax.imshow(np.transpose(clip[:, :, :], (1, 2, 0)) * 2)
            cplot.canvas.draw(); cplot.show(); cplot.exec_()
            """
            for i in range(n_b):
                temp = clip[i, :, :]
                temp = temp[transp[:, :] != 0]
                newGD.append(temp)
            newData = np.array(newGD).T
            if c_class in dic_groundReference:
                newData = np.concatenate((dic_groundReference[c_class], newData), axis = 0)
            dic_groundReference[c_class] = newData
        return dic_groundReference

    def getConnection(self):
        name = s.value('WallacePlugins/connectionName')
        self.serverName = s.value("PostgreSQL/connections/%s/host" % name)
        self.database = s.value("PostgreSQL/connections/%s/database" % name)
        self.port = "5432"
        self.usr = s.value("PostgreSQL/connections/%s/username" % name)
        self.pw = s.value("PostgreSQL/connections/%s/password" % name)
        connectionString = "PG:dbname='%s' host='%s' port='%s' user='%s'password='%s'" % (self.database, self.serverName, self.port, self.usr, self.pw)
        self.db = QtSql.QSqlDatabase("QPSQL")
        self.db.setHostName(self.serverName);
        self.db.setDatabaseName(self.database);
        self.db.setUserName(self.usr);
        self.db.setPassword(self.pw);
        ok = self.db.open();
        return connectionString

    def world2Pixel(self, geoMatrix, x, y):
            ulX = geoMatrix[0]
            ulY = geoMatrix[3]
            xDist = geoMatrix[1]
            yDist = geoMatrix[5]
            rtnX = geoMatrix[2]
            rtnY = geoMatrix[4]
            pixel = int((x - ulX) / xDist)
            line = int((ulY - y) / xDist)
            return (pixel, line)

    def imageToArray(self, i):
        a = gdalnumeric.fromstring(i.tobytes(), 'b')
        a.shape = i.im.size[1], i.im.size[0]
        return a

    def WriteGeotiffNBand(self, raster, filepath, dtype, vectReference, proj):
        nrows, ncols, n_b = np.shape(raster)
        driver = gdal.GetDriverByName("GTiff")
        dst_ds = driver.Create(filepath, ncols, nrows, n_b, dtype, ['COMPRESS=LZW'])
        dst_ds.SetProjection(proj)
        dst_ds.SetGeoTransform(vectReference)
        for i in range(n_b):
            R = np.array(raster[:, :, i], dtype = np.float32)
            dst_ds.GetRasterBand(i + 1).WriteArray(R)  # Red
            dst_ds.GetRasterBand(i + 1).SetNoDataValue(-1)
        dst_ds = None
