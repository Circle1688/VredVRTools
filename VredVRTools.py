def vredMainWindow(id):
    from shiboken2 import wrapInstance
    return wrapInstance(id, QtWidgets.QMainWindow)
# Import vred modules in a try-catch block to prevent any errors
# Abort plugin initialization when an error occurs
importError = False
try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from vrKernelServices import vrdNode, vrdGeometryNode, vrScenegraphTypes, vrdVirtualTouchpadButton, vrdDecoreSettings, vrGeometryTypes, vrMaterialTypes

    import vrController
    import vrFileIO
    import csv
    import os
    import random
    import string
    import vrScenegraph
    import vrOptimize
    import vrMaterialPtr
    import re
    import vrNodePtr
    import vrNodeUtils
    import vrFieldAccess
    import vrGeometryEditor
    import vrFileDialog
except ImportError:
    importError = True
    pass

try:
    from DatasmithExporter.exporter import DatasmithFBXExporter
except:
    pass

import uiTools

version = 'V1.4 - VRED 2023.2 -'

# Load a pyside form and the widget base from a ui file that describes the layout
form, base = uiTools.loadUiType('VredVRTools.ui')


class VredVRTools(form, base):

    """
    Main plugin class
    Inherits from fhe form and the widget base that was generated from the ui-file
    """


    def __init__(self, parent=None):
        """Setup and connect the plugins user interface"""

        super(VredVRTools, self).__init__(parent)
        parent.layout().addWidget(self)
        self.parent = parent
        self.setupUi(self)
        self.setupUserInterface()

        self.thresholdValue = 0
        self.sizethresholdValue = 0

        self.refFilename = ''
        self.matMatchMode = 0
        self.materialList = []
        self.fileopenpath = ''

        self.renamed_item = []

        self.dialog = None
        self.selmats = None
        self.optimization_dialog = None
        self.brush_dialog = None
        self.vrtools_dialog = None
        self.matchdialog = None
        self.ue_material = None

        self._pbar.setRange(0, 100)
        self._pbar.reset()


    def setupUserInterface(self):
        """Setup and connect the plugins user interface"""

        global version

        self._label.setPixmap(QtGui.QPixmap(".\icon\icon_vr.png").scaled(100, 50, QtCore.Qt.KeepAspectRatio))
        self._label.setAlignment(QtCore.Qt.AlignCenter)

        self._versionlabel.setText(version)
        self._versionlabel.setAlignment(QtCore.Qt.AlignCenter)

        self._merge.clicked.connect(self.mergeSelGeos)
        self._merge.setIcon(QtGui.QIcon(".\icon\icon_merge.png"))
        self._merge.setIconSize(QtCore.QSize(32, 32))

        self._optimization.clicked.connect(self.optimization_menu)
        self._optimization.setIcon(QtGui.QIcon(".\icon\icon_optimization.png"))
        self._optimization.setIconSize(QtCore.QSize(32, 32))

        self._materialBrush.clicked.connect(self.materialbrush)
        self._materialBrush.setIcon(QtGui.QIcon(".\icon\icon_material.png"))
        self._materialBrush.setIconSize(QtCore.QSize(32, 32))

        self._datamaterial.clicked.connect(self.datamaterials)
        self._datamaterial.setIcon(QtGui.QIcon(".\icon\icon_material_search.png"))
        self._datamaterial.setIconSize(QtCore.QSize(32, 32))

        self._export2UE.clicked.connect(self.export2UE)
        self._export2UE.setIcon(QtGui.QIcon(".\icon\icon_export.png"))
        self._export2UE.setIconSize(QtCore.QSize(32, 32))

        self._vrTools.clicked.connect(self.VR_Tools)
        self._vrTools.setIcon(QtGui.QIcon(".\icon\icon_vrtool.png"))
        self._vrTools.setIconSize(QtCore.QSize(32, 32))

    # 用于遍历几何体的函数
    def findGeosRecursive(self, node, geos, predicate):
        """ Recursively traverses the scenegraph starting at node
            and collects geometry nodes which can be filtered
            with a predicate.
            Args:
                node (vrdNode): Currently traversed node
                geos (list of vrdGeometryNode): List of collected geometry nodes
                predicate (function): None or predicate(vrdGeometryNode)->bool
        """
        geo = vrdGeometryNode(node)
        if geo.isValid():
            if predicate is None or predicate(geo):
                geos.append(geo)
            # stop traversing the tree
        else:
            # traverse the children
            for child in node.getChildren():
                self.findGeosRecursive(child, geos, predicate)


    def optimization_menu(self):

        def reject():
            self.optimization_dialog = None

        if not self.optimization_dialog:
            normal_Btn = QtWidgets.QPushButton('统一法线')
            normal_Btn.setIcon(self.get_icon('icon_normal.png'))
            normal_Btn.setIconSize(QtCore.QSize(32, 32))
            normal_Btn.clicked.connect(self.unified_Normals)

            remove_symmetry_Btn = QtWidgets.QPushButton('分割对称对象')
            remove_symmetry_Btn.setIcon(self.get_icon('icon_stitch.png'))
            remove_symmetry_Btn.setIconSize(QtCore.QSize(32, 32))
            remove_symmetry_Btn.clicked.connect(self.remove_symmetry)

            removeFace_Btn = QtWidgets.QPushButton('删除重复面')
            removeFace_Btn.setIcon(self.get_icon('icon_clear.png'))
            removeFace_Btn.setIconSize(QtCore.QSize(32, 32))
            removeFace_Btn.clicked.connect(self.removeFace)

            tessellation_Btn = QtWidgets.QPushButton('细分曲面')
            tessellation_Btn.setIcon(self.get_icon('icon_stitch.png'))
            tessellation_Btn.setIconSize(QtCore.QSize(32, 32))
            tessellation_Btn.clicked.connect(self.tessellate_surfaces)

            VBoxLayout = QtWidgets.QVBoxLayout()
            VBoxLayout.addWidget(normal_Btn)
            VBoxLayout.addWidget(remove_symmetry_Btn)
            VBoxLayout.addWidget(removeFace_Btn)
            VBoxLayout.addWidget(tessellation_Btn)

            self.optimization_dialog = QtWidgets.QDialog(self)
            self.optimization_dialog.setLayout(VBoxLayout)
            self.optimization_dialog.setWindowTitle("优化")
            self.optimization_dialog.setWindowIcon(self.get_icon('icon_optimization_Menu.png'))
            self.optimization_dialog.resize(200, 100)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.optimization_dialog.geometry()
            self.optimization_dialog.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            self.optimization_dialog.show()
            self.optimization_dialog.rejected.connect(reject)


    def remove_symmetry(self):
        '''
        分割对称几何体的函数
        '''
        nodes = vrScenegraph.getSelectedNodes()
        for node in nodes:
            # 判断是否为对称几何体
            nodeBBC = vrNodeUtils.getBoundingBoxCenter(node, True)

            if node.getType() == 'Geometry'and nodeBBC.y() == 0:
                # 创建对称节点
                childnodes = vrdNode(node).getChildren()
                parent = vrNodePtr.toNode(vrdNode(node).getParent().getObjectId())
                name = node.getName() + '_' + 'symmetry'
                symmetry_node = vrScenegraph.createNode('Shell', name, parent)
                vrScenegraph.updateScenegraph(True)

                # 移动子曲面至对称节点
                for child in childnodes:
                    BBC = vrNodeUtils.getBoundingBoxCenter(child, True)
                    if BBC.y() < 0:
                        vrScenegraph.moveNode(child, node, symmetry_node)

                # 应用原几何体材质
                vrdNode(symmetry_node).applyMaterial(vrdNode(node).getMaterial())

                # 选择对称节点
                vrScenegraph.selectNodes([node, symmetry_node], True)




    def tessellate_surfaces(self):

        def getBoundingBox(node):
            return vrNodePtr.toNode(node.getObjectId()).getBoundingBox()

        def compareBoundingBox(defaultBB, newBB, ToleranceValue):
            min = []
            max = []
            for idx in range(0, 3):
                min.append(defaultBB[idx] - ToleranceValue <= newBB[idx])
            for idx in range(3, 6):
                max.append(defaultBB[idx] + ToleranceValue >= newBB[idx])
            # print(min + max)
            if len(set(min + max)) != 1:
                return True

        def setQuality(text):
            if text == '粗糙':
                unifine_set('1.00', '30.00', '400.00')
            elif text == '低':
                unifine_set('0.15', '20.00', '300.00')
            elif text == '中等':
                unifine_set('0.075', '10.00', '200.00')
            elif text == '高':
                unifine_set('0.0375', '7.50', '100.00')
            pass

        def unifine_set(chordalDeviation, normalTolerance, maxChordLength):
            chordalDeviation_LE.setText(chordalDeviation)
            normalTolerance_LE.setText(normalTolerance)
            maxChordLength_LE.setText(maxChordLength)



        nodes = vrScenegraph.getSelectedNodes()
        if len(nodes) != 0:
            Validator = QtGui.QDoubleValidator()
            quality = ['粗糙', '低', '中等', '高']

            quality_label = QtWidgets.QLabel('细分质量：')
            quality_combobox = QtWidgets.QComboBox()
            quality_combobox.addItems(quality)
            quality_combobox.activated[str].connect(setQuality)
            quality_combobox.setCurrentIndex(2)


            chordalDeviation_label = QtWidgets.QLabel('弦偏离：')
            chordalDeviation_LE = QtWidgets.QLineEdit()
            chordalDeviation_LE.setValidator(Validator)

            normalTolerance_label = QtWidgets.QLabel('法线公差：')
            normalTolerance_LE = QtWidgets.QLineEdit()
            normalTolerance_LE.setValidator(Validator)

            maxChordLength_label = QtWidgets.QLabel('最大弦长：')
            maxChordLength_LE = QtWidgets.QLineEdit()
            maxChordLength_LE.setValidator(Validator)

            unifine_set('0.075', '10.00', '200.00')

            enableStitching_checkBox = QtWidgets.QCheckBox('启用缝合')
            enableStitching_checkBox.setChecked(True)

            st_label = QtWidgets.QLabel('缝合公差：')
            stitchingTolerance_LE = QtWidgets.QLineEdit()
            stitchingTolerance_LE.setValidator(Validator)
            stitchingTolerance_LE.setText('0.10')
            preserveUVs_checkBox = QtWidgets.QCheckBox('保留UV')
            buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

            VBoxLayout = QtWidgets.QVBoxLayout()
            VBoxLayout.addWidget(quality_label)
            VBoxLayout.addWidget(quality_combobox)
            VBoxLayout.addWidget(chordalDeviation_label)
            VBoxLayout.addWidget(chordalDeviation_LE)
            VBoxLayout.addWidget(normalTolerance_label)
            VBoxLayout.addWidget(normalTolerance_LE)
            VBoxLayout.addWidget(maxChordLength_label)
            VBoxLayout.addWidget(maxChordLength_LE)
            VBoxLayout.addWidget(enableStitching_checkBox)
            VBoxLayout.addWidget(st_label)
            VBoxLayout.addWidget(stitchingTolerance_LE)
            VBoxLayout.addWidget(preserveUVs_checkBox)
            VBoxLayout.addWidget(buttonbox)

            dialog = QtWidgets.QDialog()
            dialog.setLayout(VBoxLayout)
            dialog.setWindowTitle('细分曲面')
            buttonbox.accepted.connect(dialog.accept)
            buttonbox.rejected.connect(dialog.reject)

            res = dialog.exec_()

            if res == dialog.Accepted:

                # 遍历获取选中的所有几何体
                process_nodes_vrdNode = []
                for node in nodes:
                    allnodes = []
                    self.findGeosRecursive(vrdNode(node), allnodes, None)
                    process_nodes_vrdNode += allnodes

                # 转换vrdNode到vrNodePtr
                process_nodes = []
                for node in process_nodes_vrdNode:
                    vrNode = vrNodePtr.toNode(node.getObjectId())
                    process_nodes.append(vrNode)

                # 储存原始边界框信息
                defaultBBs = []
                for node in process_nodes:
                    defaultBB = node.getBoundingBox()
                    defaultBBs.append(defaultBB)

                # 细分曲面
                chordalDeviation = float(chordalDeviation_LE.text())
                normalTolerance = float(normalTolerance_LE.text())
                maxChordLength = float(maxChordLength_LE.text())
                enableStitching = enableStitching_checkBox.isChecked()
                stitchingTolerance = float(stitchingTolerance_LE.text())
                preserveUVs = preserveUVs_checkBox.isChecked()

                vrGeometryEditor.tessellateSurfaces(process_nodes, chordalDeviation, normalTolerance, maxChordLength,
                                                    enableStitching,
                                                    stitchingTolerance, preserveUVs)

                # 对比边界框，在原始边界框外的曲面都将被清除
                ToleranceValue = 1
                for node in process_nodes:
                    childnodes = vrdNode(node).getChildren()
                    idx = process_nodes.index(node)
                    default = defaultBBs[idx]
                    # print(default)
                    for childnode in childnodes:
                        newBB = getBoundingBox(childnode)
                        # print(newBB)
                        if compareBoundingBox(default, newBB, ToleranceValue) == True:
                            vrScenegraph.deleteNode(childnode, True)
                            pass

        else:
            self._MessageBox('请选择对象！')


    def removeFace(self):
        """
        删除几何体下的重复面
        """
        def remove_face(node):
            """
            删除几何体的重复面
            """
            selnodes = vrdNode(node).getChildren()
            center_item = []
            for node in selnodes:
                BBC = vrNodeUtils.getBoundingBoxCenter(node, True)

                center_item.append((BBC.x(), BBC.y(), BBC.z()))

            set_item = set(center_item)

            for center in set_item:
                index = [i for i, val in enumerate(center_item) if val == center]
                if len(index) > 1:
                    PCounts = []
                    for i in index:
                        PCounts.append(vrdGeometryNode(vrdNode(node)).getPrimitiveCount())
                    if len(set(PCounts)) == 1:
                        index.pop()
                        for idx in index:
                            vrScenegraph.deleteNode(selnodes[idx], True)

        node = vrScenegraph.getSelectedNode()
        if node.getType() == 'Geometry':
            remove_face(node)
        else:
            self._MessageBox('请选择几何体！')
        pass


    def unified_Normals(self):
        settings = vrdDecoreSettings()
        settings.setResolution(1024)
        settings.setQualitySteps(8)
        settings.setCorrectFaceNormals(True)
        settings.setDecoreEnabled(False)
        settings.setSubObjectMode(vrGeometryTypes.DecoreSubObjectMode.Components)
        settings.setTransparentObjectMode(vrGeometryTypes.DecoreTransparentObjectMode.Ignore)
        treatAsCombinedObject = True

        nodesToDecore = vrNodeService.getSelectedNodes()

        if nodesToDecore != []:
            vrDecoreService.decore(nodesToDecore, treatAsCombinedObject, settings)
        else:
            self._MessageBox('请选择对象！')


    def mergeSelGeos(self):




        # 用于处理所有合并节点的函数，保留次级结构
        def mergeALLNodes(node, CurrentNodeCount, AllCount):

            # 清除变换信息
            vrOptimize.flushTransformations(node)

            nodes = []
            nodes = vrdNode(node).getChildren()

            # 初始化进度
            nodeprocess = 0

            for child in nodes:
                if vrNodePtr.toNode(child.getObjectId()).getType() != "Geometry":
                    # 合并几何体
                    mergeGeos(child)

                    # 移动合并后的几何体到根组节点
                    for eachgeo in child.getChildren():
                        vrScenegraph.moveNode(eachgeo, child, node)

                    # 清除无用节点
                    # deleteNoneNode(child)



                # 计算当前进度
                nodeprocess += 1

                if AllCount == 1:
                    currentpersent = nodeprocess / len(nodes)
                else:
                    currentpersent = (CurrentNodeCount / AllCount) + (nodeprocess / len(nodes)) * (1 / AllCount)

                self._pbar.setValue(currentpersent * 100)

            # 清除无用节点
            deleteNoneNode(node)

        # 用于清除无用节点的函数
        def deleteNoneNode(node):
            allnodes = vrdNode(node).getChildren()

            for child in allnodes:
                if vrNodePtr.toNode(child.getObjectId()).getType() != "Geometry":
                    vrScenegraph.deleteNode(child, True)


        # 用于合并几何体的函数
        def mergeGeos(node):

            # 清除变换信息
            vrOptimize.flushTransformations(node)

            # 合并几何体
            vrOptimize.mergeGeometry(node)

            # 移动所有几何体到次级节点
            MoveNodes(node)

            # 合并几何体
            vrOptimize.mergeGeometry(node)

        # 遍历所有几何体并移动
        def MoveNodes(node):

            # 遍历所有几何体
            geoNodes = []
            self.findGeosRecursive(vrdNode(node), geoNodes, None)

            # 移动合并后的几何体到根节点
            for eachgeo in geoNodes:
                vrScenegraph.moveNode(eachgeo, eachgeo.getParent(), node)



        nodes = vrScenegraph.getSelectedNodes()

        # 处理单选或多选对象
        if len(nodes) != 0:

            self._pbar.reset()


            nodeprocess = 0

            for node in nodes:
                # 清除共享关系
                vrNodeUtils.unshareCores(node)

                nodeprocess += 1

                # 合并几何体
                mergeALLNodes(node, nodeprocess, len(nodes))

            print("done merge")
            self._pbar.reset()


            self._MessageBox("合并完成！")
        else:
            self._MessageBox("请选择对象！")


    def export2UE(self):

        def reject():
            self.dialog = None

        if not self.dialog:
            ue_importMaterial_Btn = QtWidgets.QPushButton('使用UE材质重命名')
            ue_importMaterial_Btn.setIcon(self.get_icon('icon_material.png'))
            ue_importMaterial_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_importMaterial_Btn.clicked.connect(self.import_UEMaterial)

            ue_rename_Btn = QtWidgets.QPushButton('覆盖 - 重命名')
            ue_rename_Btn.setIcon(self.get_icon('icon_rename.png'))
            ue_rename_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_rename_Btn.clicked.connect(self.renameDefault)

            ue_rename_change_Btn = QtWidgets.QPushButton('修改 - 重命名')
            ue_rename_change_Btn.setIcon(self.get_icon('icon_rename.png'))
            ue_rename_change_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_rename_change_Btn.clicked.connect(self.renameChange)

            datasmith_Btn = QtWidgets.QPushButton('导出Datasmith')
            datasmith_Btn.setIcon(self.get_icon('icon_export.png'))
            datasmith_Btn.setIconSize(QtCore.QSize(32, 32))
            datasmith_Btn.clicked.connect(self.datasmith_menu)

            exportMaterialData = QtWidgets.QPushButton('导出UE材质替换表')
            exportMaterialData.setIcon(self.get_icon('icon_export.png'))
            exportMaterialData.setIconSize(QtCore.QSize(32, 32))
            exportMaterialData.clicked.connect(self.selectRef)

            VBoxLayout = QtWidgets.QVBoxLayout()
            VBoxLayout.addWidget(ue_rename_Btn)
            VBoxLayout.addWidget(ue_rename_change_Btn)
            VBoxLayout.addWidget(datasmith_Btn)
            VBoxLayout.addWidget(ue_importMaterial_Btn)
            VBoxLayout.addWidget(exportMaterialData)

            self.dialog = QtWidgets.QDialog(self)
            self.dialog.setLayout(VBoxLayout)
            self.dialog.setWindowTitle("导出到UE")
            self.dialog.setWindowIcon(self.get_icon('icon_export_panel.png'))
            self.dialog.resize(200, 100)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.dialog.geometry()
            self.dialog.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            self.dialog.show()
            self.dialog.rejected.connect(reject)




    def import_UEMaterial(self):

        def import_material():
            ue_Materials = []

            filedialog = QtWidgets.QFileDialog()
            self.fileopenpath = \
            filedialog.getOpenFileName(self, '导入UE材质表', os.path.join(os.path.expanduser("~"), 'Desktop'), 'CSV(*.csv)')[
                0]

            if os.path.exists(self.fileopenpath):
                encodes = ['UTF-8', 'UTF-16']
                i = 0
                while i < len(encodes):
                    try:
                        with open(self.fileopenpath, 'r', encoding=encodes[i]) as csvfile:
                            reader = csv.reader(csvfile)
                            for row in reader:
                                ue_Materials += [row[1]]
                            ue_Materials.pop(0)
                        break
                    except:
                        i += 1
                        if i > len(encodes):
                            self.fileopenpath = ''
                            self._MessageBox('导入出错！')

                ue_import_label.setText(os.path.basename(self.fileopenpath))

                self.materialList = ue_Materials

                listview.clear()

                listview.addItems(self.materialList)

        def rename():

            tag = '未重命名材质'

            if self.selmats and listview.currentItem():
                for selmat in self.selmats:
                    selmat.setName(listview.currentItem().text())
                    preview_name.setText(selmat.getName())

                    oldmat = vrMaterialPtr.toMaterial(selmat.getObjectId())
                    vrMaterialPtr.removeMaterialTag(oldmat, tag)

                self.renamed_item.append(listview.currentItem())
                hide_renamed()



        def update_search():
            for i in range(listview.count()):
                item = listview.item(i)
                item.setHidden(ue_searchbar.text().lower() not in item.text().lower() or hide_checkBox.isChecked() and item in self.renamed_item)

        def receivedMessage(message_id, args):
            # Listen specifically to the SELECTED CAMERA message
            if message_id == vrController.VRED_MSG_SELECTED_NODE:
                nodes = vrNodeService.getSelectedNodes()
                if len(nodes) == 1:
                    selmat = nodes[0].getMaterial()
                    self.selmats = [selmat]
                    preview_label.setPixmap(QtGui.QPixmap.fromImage(selmat.getPreview()).scaled(60, 60, QtCore.Qt.KeepAspectRatio))
                    preview_name.setText(selmat.getName())
                else:
                    self.selmats = []
                    for node in nodes:
                        self.selmats.append(node.getMaterial())
                    preview_name.setText("多选")


            if message_id == vrController.VRED_MSG_SELECTED_MATERIAL:
                selmats = vrMaterialService.getMaterialSelection()
                if len(selmats) == 1:
                    selmat = selmats[0]
                    preview_label.setPixmap(QtGui.QPixmap.fromImage(selmat.getPreview()).scaled(60, 60, QtCore.Qt.KeepAspectRatio))
                    preview_name.setText(selmat.getName())
                    self.selmats = [selmat]
                else:
                    self.selmats = selmats
                    preview_name.setText("多选")


        def disconnectMessage():
            vrMessageService.message.disconnect(receivedMessage)
            self.ue_material = None

        def hide_renamed():
            if hide_checkBox.isChecked() == True:
                for i in range(listview.count()):
                    item = listview.item(i)
                    item.setHidden(item in self.renamed_item or ue_searchbar.text().lower() not in item.text().lower())
            if hide_checkBox.isChecked() == False:
                for i in range(listview.count()):
                    item = listview.item(i)
                    item.setHidden(False or ue_searchbar.text().lower() not in item.text().lower())

        def tag_material():
            tag = '未重命名材质'
            for mat in vrMaterialService.getAllMaterials():
                if mat.getName() not in self.materialList:
                    oldmat = vrMaterialPtr.toMaterial(mat.getObjectId())
                    vrMaterialPtr.addMaterialTag(oldmat, tag)






        if not self.ue_material:
            self.dialog.reject()

            ue_import_label = QtWidgets.QLabel(os.path.basename(self.fileopenpath))

            ue_importMaterial_Btn = QtWidgets.QPushButton('导入UE材质表')
            ue_importMaterial_Btn.setIcon(self.get_icon('icon_export.png'))
            ue_importMaterial_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_importMaterial_Btn.clicked.connect(import_material)

            ue_tagMaterial_Btn = QtWidgets.QPushButton('标记未重命名材质')
            ue_tagMaterial_Btn.setIcon(self.get_icon('icon_material.png'))
            ue_tagMaterial_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_tagMaterial_Btn.clicked.connect(tag_material)

            ue_rename_Btn = QtWidgets.QPushButton('重命名材质')
            ue_rename_Btn.setIcon(self.get_icon('icon_rename.png'))
            ue_rename_Btn.setIconSize(QtCore.QSize(32, 32))
            ue_rename_Btn.clicked.connect(rename)

            ue_searchbar_label = QtWidgets.QLabel('搜索:')

            ue_searchbar = QtWidgets.QLineEdit()
            ue_searchbar.textChanged.connect(update_search)

            listview = QtWidgets.QListWidget()

            listview.addItems(self.materialList)

            hide_checkBox = QtWidgets.QCheckBox('隐藏已重命名项')
            hide_checkBox.stateChanged.connect(hide_renamed)

            preview_alabel = QtWidgets.QLabel('当前选择的材质:')
            preview_label = QtWidgets.QLabel()
            preview_name = QtWidgets.QLabel()

            VBoxLayout = QtWidgets.QVBoxLayout()
            VBoxLayout.addWidget(ue_import_label)
            VBoxLayout.addWidget(ue_importMaterial_Btn)
            VBoxLayout.addWidget(ue_tagMaterial_Btn)
            VBoxLayout.addWidget(ue_searchbar_label)
            VBoxLayout.addWidget(ue_searchbar)
            VBoxLayout.addWidget(hide_checkBox)
            VBoxLayout.addWidget(listview)
            VBoxLayout.addWidget(preview_alabel)
            VBoxLayout.addWidget(preview_label)
            VBoxLayout.addWidget(preview_name)
            VBoxLayout.addWidget(ue_rename_Btn)

            self.ue_material = QtWidgets.QDialog(self)
            self.ue_material.setLayout(VBoxLayout)
            self.ue_material.setWindowTitle("使用UE材质重命名")
            self.ue_material.setWindowIcon(self.get_icon('icon_material_panel.png'))
            self.ue_material.resize(300, 600)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.ue_material.geometry()
            self.ue_material.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            self.ue_material.show()
            vrMessageService.message.connect(receivedMessage)
            self.ue_material.rejected.connect(disconnectMessage)






    def datasmith_menu(self):

        self.dialog.reject()

        optimization_label = QtWidgets.QLabel('优化选项：')

        clear_environment_checkBox = QtWidgets.QCheckBox('删除环境几何体')
        clear_environment_checkBox.setChecked(True)

        clear_unusable_checkBox = QtWidgets.QCheckBox('清理无用项')
        clear_unusable_checkBox.setChecked(True)

        clear_texture_checkBox = QtWidgets.QCheckBox('清理材质贴图')
        clear_texture_checkBox.setChecked(True)

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        VBoxLayout = QtWidgets.QVBoxLayout()
        VBoxLayout.addWidget(optimization_label)
        VBoxLayout.addWidget(clear_environment_checkBox)
        VBoxLayout.addWidget(clear_unusable_checkBox)
        VBoxLayout.addWidget(clear_texture_checkBox)
        VBoxLayout.addWidget(buttonbox)

        dialog = QtWidgets.QDialog()
        dialog.setLayout(VBoxLayout)
        dialog.setWindowTitle('导出Datasmith')

        buttonbox.accepted.connect(dialog.accept)
        buttonbox.rejected.connect(dialog.reject)

        res = dialog.exec_()

        if res == dialog.Accepted:

            currentScenePath = vrFileIO.getFileIOFilePath()

            if len(currentScenePath) == 0:
                currentScenePath = vrFileDialog.getSaveFileName("Save As", "", ["vpb(*.vpb)"], True)

            currentScenePath = os.path.splitext(currentScenePath)[0] + '.vpb'

            vrFileIO.save(currentScenePath)

            if clear_environment_checkBox.isChecked() == True:
                self.clear_environments()
            if clear_unusable_checkBox.isChecked() == True:
                self.clear_unusable()
            if clear_texture_checkBox.isChecked() == True:
                self.clearTextures()

            self.datasmith()
        pass


    def datasmith(self):
        try:
            self.exporter = DatasmithFBXExporter(vredMainWindow(VREDMainWindowId))
            self.exporter.exportSceneDialog()
        except:
            self._MessageBox('缺少Datasmith插件！')


    def clear_environments(self):
        name = 'Studio'

        vrNodeService.initFindCache()
        node = vrNodeService.findNode(name)
        vrNodeService.clearFindCache()

        for childnode in node.getChildren():
            vrScenegraph.deleteNode(vrNodePtr.toNode(childnode.getObjectId()), True)


    def clear_unusable(self):
        node = vrScenegraph.getRootNode()
        vrOptimize.removeEmptyGeometries(node)
        vrOptimize.removeEmptyShells(node)
        vrOptimize.cleanupGroupNodes(node, True)


    def clearTextures(self):
        mats = vrMaterialPtr.getAllMaterials()
        data = ['diffuse', 'glossy', 'specular', 'incandescence', 'bump', 'transparency', 'scatter', 'roughness',
                'displacement', 'fresnel', 'rotation', 'indexOfRefraction', 'specularBump', 'metallic',
                'ambientOcclusion']
        for mat in mats:
            for fname in data:
                colorComponentData = vrFieldAccess.vrFieldAccess(mat.fields().getFieldContainer('colorComponentData'))
                Component = vrFieldAccess.vrFieldAccess(colorComponentData.getFieldContainer(fname + 'Component'))
                Component.setBool("useTexture", False)

            # print('Done')
        # self._MessageBox('已清除所有材质贴图！')


    def selectRef(self):

        def opendialog():
            filedialog = QtWidgets.QFileDialog()
            fileopenpath = filedialog.getOpenFileName(dialog, '选择UE材质替换参考表', os.path.join(os.path.expanduser("~"), 'Desktop'), 'CSV(*.csv)')[0]
            filename = os.path.basename(fileopenpath)
            Alineedit.setText(filename)
            self.refFilename = fileopenpath

        self.dialog.reject()

        Alineedit = QtWidgets.QLineEdit()
        Alineedit.setReadOnly(True)
        Alabel = QtWidgets.QLabel('参考表：')
        Bopen = QtWidgets.QPushButton('选择参考表')
        Bopen.setIcon(QtGui.QIcon(self.get_icon('icon_csv.png')))
        Bopen.setIconSize(QtCore.QSize(32, 32))
        Bopen.clicked.connect(opendialog)
        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        Blabel = QtWidgets.QLabel('材质替换模式：')
        combobox = QtWidgets.QComboBox()
        combobox.addItem('包含')
        combobox.addItem('精确匹配')


        VBoxLayout = QtWidgets.QVBoxLayout()
        VBoxLayout.addWidget(Blabel)
        VBoxLayout.addWidget(combobox)
        VBoxLayout.addWidget(Alabel)
        VBoxLayout.addWidget(Alineedit)
        VBoxLayout.addWidget(Bopen)
        VBoxLayout.addWidget(buttonbox)

        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("导出UE材质替换表")
        dialog.setLayout(VBoxLayout)
        dialog.resize(300, 100)
        buttonbox.accepted.connect(dialog.accept)
        buttonbox.rejected.connect(dialog.reject)

        res = dialog.exec_()
        if res == dialog.Accepted:
            self.matMatchMode = combobox.currentIndex()
            if Alineedit.text() == '':
                self.refFilename = ''

            self.exportMaterialData()


    def exportMaterialData(self):

        filename = os.path.splitext(os.path.basename(vrFileIO.getFileIOFilePath()))[0]
        defaultname = filename + '_MaterialData.csv'
        dialog = QtWidgets.QFileDialog()
        savefilepath = dialog.getSaveFileName(self, '选择保存路径', os.path.join(os.path.join(os.path.expanduser("~"), 'Desktop'), defaultname), 'CSV(*.csv)')[0]

        if savefilepath != '':

            rowName = []
            searchstring = []
            stringMatch = []
            materialReplacement = []
            dict_materialReplacement = {}

            mats = vrMaterialPtr.getAllMaterials()

            if self.matMatchMode == 0:
                print('yes')
                # for mat in oldmatsname:
                #     newMatname = re.sub(u"([^\u4E00-\u9FA5\uf900-\ufa2d\u0041-\u005a\u0061-\u007a])", "", mat)
                #     rowName.append(newMatname)
                #     rowName = sorted(set(rowName), key=rowName.index)
                for mat in mats:
                    newMatname = re.sub(u"([^\u4E00-\u9FA5\uf900-\ufa2d\u0041-\u005a\u0061-\u007a\u005f])", "", mat.getName())
                    searchstring.append(newMatname)
                    searchstring = sorted(set(searchstring), key=searchstring.index)

                for row in searchstring:
                    # text = translator.translate(row)
                    # result = text.translatedText
                    # result = result.replace(' ', '_')
                    rowName.append(row)

                i = 0
                for i in range(0, len(searchstring)):
                    stringMatch.append('Contains')
                    i += 1

            if self.matMatchMode == 1:
                print('no')
                # for mat in oldmatsname:
                #     rowName.append(mat)

                for mat in mats:
                    # text = translator.translate(mat.getName())
                    # result = text.translatedText
                    # result = result.replace(' ', '_')
                    rowName.append(mat.getName())
                    searchstring.append(mat.getName())

                i = 0
                for i in range(0, len(mats)):
                    stringMatch.append('Exact Match')
                    i += 1

            if self.refFilename != '':
                row1 = []
                row2 = []
                with open(self.refFilename, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        row1 += [row[1]]
                        row2 += [row[3]]
                    dict_materialReplacement = dict(zip(row1, row2))
                    dict_materialReplacement.pop('SearchString')

            for search in searchstring:
                materialReplacement.append(dict_materialReplacement.get(search))





            # 写入文件

            try:
                with open(savefilepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=",")
                    header = ['Row Name', 'Search String', 'String Match', 'Material Replacement']
                    writer.writerow(header)
                    writer.writerows(zip(rowName, searchstring, stringMatch, materialReplacement))
                self._MessageBox('导出成功！')

            except:
                self._MessageBox('写入错误！\n请检查文件是否在其他程序中使用！')


    def _MessageBox(self, message):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setWindowTitle("VredVRTools")
        msgBox.setInformativeText(message)
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msgBox.exec_()

    def GetNodeBasename(self, node):
        node_basename = ''
        try:
            idx = int(node.getName().split('_')[-1])
        except ValueError:
            node_basename = node.getName()
        else:
            if idx > 10000000:
                node_basename = node.getName()
            else:
                # 移除原本数字后缀，重新给上数字后缀，记录当前所用最大值
                node_basename = node.getName().strip('_' + str(idx))
        finally:
            return node_basename

    def Rename_default_Recursive(self, node):

        def rename():
            node_basename = self.GetNodeBasename(node)
            # 恢复base名
            node.setName(node_basename)
            # 重命名
            for childgeo in geos:
                childgeo.setName(node_basename + '_' + str(geos.index(childgeo)))

            node.setName(node_basename + '_' + str(len(geos)))

        geos = []
        others = []

        for child in node.getChildren():
            geo = vrdGeometryNode(child)
            if geo.isValid():
                geos.append(geo)
            else:
                others.append(child)

        # 尝试找出数字后缀
        try:
            has_idx = int(node.getName().split('_')[-1])

        # 如果类型转换错误，即后缀并不是数字类型
        except ValueError:

            # 子几何体数量不为空时，增加后缀来记录当前使用的最大数字值，避免后面出现几何体数字后缀重复使用的情况
            if len(geos) != 0:
                # 重命名
                rename()

        # 如果类型转换成功
        else:

            # 子几何体数量不为空时，且非日期形式
            if len(geos) != 0:
                # 重命名
                rename()
        finally:

            # 递归遍历
            for child in others:
                self.Rename_default_Recursive(child)

    def Rename_change_Recursive(self, node):
        geos = []
        others = []

        for child in node.getChildren():
            geo = vrdGeometryNode(child)
            if geo.isValid():
                geos.append(geo)
            else:
                others.append(child)


        # 将已经使用的数字加入集合
        i = 0
        try:
            has_idx = int(node.getName().split('_')[-1])
        except ValueError:
            pass
        else:
            i = has_idx
        finally:
            node_basename = self.GetNodeBasename(node)

            for childgeo in geos:
                child_name = childgeo.getName()
                if node_basename not in child_name:
                    childgeo.setName(node_basename + '_' + str(i))
                    i += 1

            if len(geos) != 0:
                node.setName(node_basename + '_' + str(i))

            # 递归遍历
            for child in others:
                self.Rename_change_Recursive(child)


    def renameDefault(self):

        node = vrScenegraph.getRootNode()

        vrUndoService.beginUndo()
        vrUndoService.beginMultiCommand("rename_default")

        self.Rename_default_Recursive(vrdNode(node))

        vrUndoService.endMultiCommand()
        vrUndoService.endUndo()

    def renameChange(self):

        node = vrScenegraph.getRootNode()

        vrUndoService.beginUndo()
        vrUndoService.beginMultiCommand("rename_change")

        self.Rename_change_Recursive(vrdNode(node))

        vrUndoService.endMultiCommand()
        vrUndoService.endUndo()




    def datamaterials(self):

        def selectoldnode():
            oldnode = vrScenegraph.getSelectedNode()
            Alineedit.setText(oldnode.getName())
            self.selectedoldnode = oldnode

        def selectnewnode():
            newnode = vrScenegraph.getSelectedNode()
            Blineedit.setText(newnode.getName())
            self.selelctednewnode = newnode

        def accept():
            if Alineedit.text() == '' or Blineedit.text() == '':
                self._MessageBox('请选择节点！')
            else:
                self.thresholdValue = int(Clineedit.text())
                self.sizethresholdValue = int(Dlineedit.text())
                self.matchdialog.close()

                vrUndoService.beginUndo()
                vrUndoService.beginMultiCommand("MatchMaterial")
                try:
                    self.materialsCore(self.selectedoldnode, self.selelctednewnode)
                except:
                    pass
                finally:
                    vrUndoService.endMultiCommand()
                    vrUndoService.endUndo()

        def reject():
            self.matchdialog = None


        if not self.matchdialog:
            buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

            Alineedit = QtWidgets.QLineEdit()
            Alineedit.setReadOnly(True)
            Blineedit = QtWidgets.QLineEdit()
            Blineedit.setReadOnly(True)

            Clineedit = QtWidgets.QLineEdit()
            Clineedit.setValidator(QtGui.QIntValidator())
            Clineedit.setText("0")
            Dlineedit = QtWidgets.QLineEdit()
            Dlineedit.setValidator(QtGui.QIntValidator())
            Dlineedit.setMaxLength(3)
            Dlineedit.setText("100")
            Alabel = QtWidgets.QLabel("位置阈值（单位mm）:")
            Blabel = QtWidgets.QLabel("边界框相似度阈值 %:")

            selectOld = QtWidgets.QPushButton('选择参考节点')
            selectOld.setIcon(QtGui.QIcon(self.get_icon('icon_material_select.png')))
            selectOld.setIconSize(QtCore.QSize(32, 32))
            ABlabel = QtWidgets.QLabel("参考节点:")

            selectNew = QtWidgets.QPushButton('选择匹配节点')
            selectNew.setIcon(QtGui.QIcon(self.get_icon('icon_material_select.png')))
            selectNew.setIconSize(QtCore.QSize(32, 32))
            BBlabel = QtWidgets.QLabel("匹配节点:")

            AAAlabel = QtWidgets.QLabel()

            VBoxLayout = QtWidgets.QVBoxLayout()
            VBoxLayout.addWidget(ABlabel)
            VBoxLayout.addWidget(Alineedit)
            VBoxLayout.addWidget(selectOld)
            VBoxLayout.addWidget(BBlabel)
            VBoxLayout.addWidget(Blineedit)
            VBoxLayout.addWidget(selectNew)
            VBoxLayout.addWidget(AAAlabel)
            VBoxLayout.addWidget(Alabel)
            VBoxLayout.addWidget(Clineedit)
            VBoxLayout.addWidget(Blabel)
            VBoxLayout.addWidget(Dlineedit)
            VBoxLayout.addWidget(AAAlabel)
            VBoxLayout.addWidget(buttonbox)

            self.matchdialog = QtWidgets.QDialog(self)
            self.matchdialog.setWindowTitle("匹配材质")
            self.matchdialog.setWindowIcon(self.get_icon('icon_material_search_panel.png'))
            self.matchdialog.setLayout(VBoxLayout)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.matchdialog.geometry()
            self.matchdialog.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            buttonbox.accepted.connect(accept)
            buttonbox.rejected.connect(self.matchdialog.reject)

            selectOld.clicked.connect(selectoldnode)
            selectNew.clicked.connect(selectnewnode)

            self.matchdialog.show()
            self.matchdialog.rejected.connect(reject)






    def materialsCore(self, oldnode, newnode):

        # 计算空间向量距离的函数
        def CalVectorLength(vector1, vector2):
            x1 = vector1.x()
            y1 = vector1.y()
            z1 = vector1.z()
            x2 = vector2.x()
            y2 = vector2.y()
            z2 = vector2.z()
            length = pow(pow(x1 - x2, 2) + pow(y1 - y2, 2) + pow(z1 - z2, 2), 0.5)
            return length

        # 获取边界框最大最小坐标，返回对角线向量
        def getBoundingBoxVector(node):
            bx = vrNodePtr.toNode(node.getObjectId()).getBoundingBox()
            x1 = bx[0]
            y1 = bx[1]
            z1 = bx[2]
            x2 = bx[3]
            y2 = bx[4]
            z2 = bx[5]
            vector = [x1 - x2, y1 - y2, z1 - z2]
            return vector

        # 获取向量长度
        def getvectorlength(vector):
            x = vector[0]
            y = vector[1]
            z = vector[2]
            length = pow(pow(x, 2) + pow(y, 2) + pow(z, 2), 0.5)
            return length

        # 计算向量余弦相似度，取值[-1,1]，cos = 1，夹角=0，最相似；cos = 0，夹角=90，不相似；cos = -1，方向相反
        def cos_sim(vector1, vector2):
            x1 = vector1[0]
            y1 = vector1[1]
            z1 = vector1[2]
            x2 = vector2[0]
            y2 = vector2[1]
            z2 = vector2[2]
            upnum = x1 * x2 + y1 * y2 + z1 * z2
            lownum = pow(pow(x1, 2) + pow(y1, 2) + pow(z1, 2), 0.5) * pow(pow(x2, 2) + pow(y2, 2) + pow(z2, 2), 0.5)
            if lownum != 0:
                cos = upnum / lownum
            else:
                cos = 0
            return cos


        # 计算比较百分比
        def Calpercent(a,b):
            percent = 1
            if a < b:
                if b != 0:
                    percent = a / b
                else:
                    percent = 0
            if a > b:
                if a != 0:
                    percent = b / a
                else:
                    percent = 0

            return percent


        self._pbar.reset()

        # 遍历老数据对象
        oldgeonodes = []
        self.findGeosRecursive(vrdNode(oldnode), oldgeonodes, None)

        oldVectors = []  # 定义老数据对象中心点数组

        olddict = {}  # 定义老对象字典，key=中心点，value=边界框大小


        # 循环添加中心点到数组，为字典添加内容
        for oldgeonode in oldgeonodes:
            oldvector = vrNodeUtils.getBoundingBoxCenter(oldgeonode, False)
            oldbxvector = getBoundingBoxVector(oldgeonode)
            oldVectors.append(oldvector)
            olddict[oldvector] = oldbxvector

        print("Old Data Done")

        # 遍历新数据对象
        newgeonodes = []
        self.findGeosRecursive(vrdNode(newnode), newgeonodes, None)

        # 统一赋予检查材质
        mat = vrMaterialPtr.findMaterial('CheckMat')
        if mat.getName() == None:
            mat = vrMaterialPtr.createMaterial("UPlasticMaterial")
            mat.setName('CheckMat')
            mat.fields().setVec3f("diffuseColor", 0, 1, 0)
            mat.fields().setVec4f("incandescenceColor", 0, 1, 0, 1)

        for newgeonode in newgeonodes:
            newgeonode.applyMaterial(mat)

        nodeprocess = 0

        # 循环新对象节点，查找老对象数组和字典，通过阈值对中心点位置差异和边界框大小进行比较，符合条件则替换材质
        for newgeonode in newgeonodes:
            newvector = vrNodeUtils.getBoundingBoxCenter(newgeonode, False)  # 获取边界框中心位置
            newbxvector = getBoundingBoxVector(newgeonode)  # 获取边界框对角线向量
            newbxsize = getvectorlength(newbxvector)  # 获取边界框向量长度
            for oldvector in oldVectors:

                oldbxvector = olddict[oldvector]
                oldbxsize = getvectorlength(oldbxvector)
                oldgeonode = oldgeonodes[oldVectors.index(oldvector)]

                dist = CalVectorLength(oldvector, newvector)  # 计算中心点差值
                cossim = cos_sim(oldbxvector, newbxvector)  # 计算边界框对角线向量相似度
                bxsizediff = Calpercent(oldbxsize, newbxsize) * 100  # 计算边界框向量长度相似度

                # 计算面数相似度
                a = oldgeonode.getChildCount()
                b = newgeonode.getChildCount()
                componentcount = Calpercent(a, b)

                _thresholdValue = self.thresholdValue  # 获得中心点阈值
                sizeThresholdValue = self.sizethresholdValue  # 定义边界框大小阈值

                # 如果中心点差值<=阈值，再判断边界框对角线向量相似度，再判断组件个数，符合条件则判断是否为一个件替换材质
                if dist <= _thresholdValue:
                    if bxsizediff >= sizeThresholdValue:
                        if cossim >= 0.8:
                            if componentcount >= 0.5:
                                newgeonode.applyMaterial(oldgeonode.getMaterial())  # 获取节点并替换材质


            nodeprocess += 1
            currentpersent = nodeprocess / len(newgeonodes)
            self._pbar.setValue(currentpersent * 100)

        self._pbar.reset()

        self._MessageBox("新对象材质替换完成！")


    def vrlock(self):
        vrImmersiveInteractionService.setViewpointMode(True, True, True)
        # Get the left controller
        leftController = vrDeviceService.getVRDevice("left-controller")
        # Get the right controller
        rightController = vrDeviceService.getVRDevice("right-controller")

        # Define the description of the virtual buttons on the touchpad.
        # These description consist of a name, a radius 0 - 1 and an angle 0 - 360,
        # where on the circular touchpad the button is located
        padCenter = vrdVirtualTouchpadButton("padcenter", 0.0, 0.0, 0.0, 0.0)
        padLeft = vrdVirtualTouchpadButton("padleft", 0.0, 0.0, 0.0, 0.0)
        padUp = vrdVirtualTouchpadButton("padup", 0.0, 0.0, 0.0, 0.0)
        padRight = vrdVirtualTouchpadButton("padright", 0.0, 0.0, 0.0, 0.0)
        padDown = vrdVirtualTouchpadButton("paddown", 0.0, 0.0, 0.0, 0.0)


        # Add the descirptions for the virtual buttons to the left controller
        leftController.addVirtualButton(padCenter, "touchpad")
        leftController.addVirtualButton(padLeft, "touchpad")
        leftController.addVirtualButton(padUp, "touchpad")
        leftController.addVirtualButton(padRight, "touchpad")
        leftController.addVirtualButton(padDown, "touchpad")

        # Also add the descriptions to the right controller
        # Note that each controller can have different tochpad layouts, if
        # it is needed.
        rightController.addVirtualButton(padLeft, "touchpad")
        rightController.addVirtualButton(padUp, "touchpad")
        rightController.addVirtualButton(padRight, "touchpad")
        rightController.addVirtualButton(padDown, "touchpad")
        rightController.addVirtualButton(padCenter, "touchpad")

        # Get the interaction which actions should be remapped to the virtual buttons
        teleport = vrDeviceService.getInteraction("Teleport")
        # Set the mapping of the actions to the new virtual buttons
        teleport.setControllerActionMapping("prepare", "any-paddown-touched")
        teleport.setControllerActionMapping("abort", "any-paddown-untouched")
        teleport.setControllerActionMapping("execute", "any-paddown-pressed")

        self._MessageBox("已锁定触摸板！")


    def materialbrush(self):

        def click_record():
            node = vrScenegraph.getSelectedNode()
            self.mat = vrdNode(node).getMaterial()
            mat_img.setPixmap(QtGui.QPixmap.fromImage(self.mat.getPreview()).scaled(60, 60, QtCore.Qt.KeepAspectRatio))
            mat_lineedit.setText(self.mat.getName())

        def click_select_all():
            node = vrScenegraph.getSelectedNode()
            allnodes = node.getMaterial().getNodes()
            selnodes = []
            for node in allnodes:
                if vrdNode(node).isVisible() == True:
                    selnodes.append(node)

            vrScenegraph.selectNodes(selnodes)


        def click_apply():
            nodes = vrScenegraph.getSelectedNodes()
            if len(nodes) != 0:
                vrUndoService.beginUndo()
                vrUndoService.beginMultiCommand("applyMaterial")
                try:
                    for node in nodes:
                        vrdNode(node).applyMaterial(self.mat)
                    preview_label.setPixmap(QtGui.QPixmap.fromImage(self.mat.getPreview()).scaled(60, 60, QtCore.Qt.KeepAspectRatio))
                    preview_name.setText(self.mat.getName())
                except:
                    pass
                finally:
                    vrUndoService.endMultiCommand()
                    vrUndoService.endUndo()

        def reject():
            self.brush_dialog = None


        if not self.brush_dialog:
            mat_label = QtWidgets.QLabel('当前记录的材质:')
            mat_img = QtWidgets.QLabel()
            mat_lineedit = QtWidgets.QLabel()

            alabel = QtWidgets.QLabel()

            record_Btn = QtWidgets.QPushButton('记录材质')
            record_Btn.setIcon(QtGui.QIcon(self.get_icon('icon_material_record.png')))
            record_Btn.setIconSize(QtCore.QSize(32, 32))
            record_Btn.clicked.connect(click_record)

            selectBtn = QtWidgets.QPushButton('选择材质相同项')
            selectBtn.setIcon(QtGui.QIcon(self.get_icon('icon_material_select.png')))
            selectBtn.setIconSize(QtCore.QSize(32, 32))
            selectBtn.clicked.connect(click_select_all)

            apply_Btn = QtWidgets.QPushButton('赋予已记录材质')
            apply_Btn.setIcon(QtGui.QIcon(self.get_icon('icon_material_apply.png')))
            apply_Btn.setIconSize(QtCore.QSize(32, 32))
            apply_Btn.clicked.connect(click_apply)

            vbox = QtWidgets.QVBoxLayout()

            vbox.addWidget(mat_label)
            vbox.addWidget(mat_img)
            vbox.addWidget(mat_lineedit)
            vbox.addWidget(alabel)
            vbox.addWidget(record_Btn)
            vbox.addWidget(selectBtn)
            vbox.addWidget(apply_Btn)

            self.brush_dialog = QtWidgets.QDialog(self)
            self.brush_dialog.setLayout(vbox)
            self.brush_dialog.setWindowTitle('材质刷')
            self.brush_dialog.setWindowIcon(self.get_icon('icon_material_panel.png'))
            self.brush_dialog.resize(180, 100)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.brush_dialog.geometry()
            self.brush_dialog.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            self.brush_dialog.show()
            self.brush_dialog.rejected.connect(reject)



    def get_icon(self, icon):
        icondir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon')
        return QtGui.QIcon(os.path.join(icondir, icon))


    def VR_Tools(self):

        def reject():
            self.vrtools_dialog = None

        if not self.vrtools_dialog:
            self._vrlock = QtWidgets.QPushButton('锁定触摸板')
            self._vrlock.setIcon(QtGui.QIcon(self.get_icon('icon_vrlock.png')))
            self._vrlock.setIconSize(QtCore.QSize(32, 32))
            self._vrlock.clicked.connect(self.vrlock)

            self._vrSelect = QtWidgets.QPushButton('启用/关闭 指针选择')
            self._vrSelect.setIcon(QtGui.QIcon(self.get_icon('icon_normal.png')))
            self._vrSelect.setIconSize(QtCore.QSize(32, 32))
            self._vrSelect.setCheckable(True)
            self._vrSelect.clicked.connect(self.vr_select)

            vbox = QtWidgets.QVBoxLayout()
            vbox.addWidget(self._vrlock)
            vbox.addWidget(self._vrSelect)

            self.vrtools_dialog = QtWidgets.QDialog(self)
            self.vrtools_dialog.setLayout(vbox)
            self.vrtools_dialog.setWindowTitle('VR工具')
            self.vrtools_dialog.setWindowIcon(self.get_icon('icon_vrTools.png'))
            self.vrtools_dialog.resize(180, 100)

            screen = QtWidgets.QDesktopWidget().screenGeometry()
            size = self.vrtools_dialog.geometry()
            self.vrtools_dialog.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

            self.vrtools_dialog.show()
            self.vrtools_dialog.rejected.connect(reject)




    def vr_select(self):
        def select(action, device):
            if self._vrSelect.isChecked():
                node = device.pick().getNode()
                print(node.getName())
                NodePtr = vrNodePtr.toNode(node.getObjectId())
                vrScenegraph.selectNode(NodePtr)

        pointer = vrDeviceService.getInteraction("Pointer")
        start = pointer.getControllerAction("start")
        start.signal().triggered.connect(select)


# Actually start the plugin
if not importError:
    VredVRTools = VredVRTools(VREDPluginWidget)