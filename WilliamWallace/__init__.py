# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WilliamWallace
                                 A QGIS plugin
 This plugin do a supervised classification
                             -------------------
        begin                : 2016-05-17
        copyright            : (C) 2016 by Gillian
        email                : gillian.milani@geo.uzh.ch
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load WilliamWallace class from file WilliamWallace.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .willian_wallace import WilliamWallace
    return WilliamWallace(iface)
