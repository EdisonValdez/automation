# -*- coding: utf-8 -*-

import xlwt

class ExportMapsData:
    
    def __init__(self, fileName, path, placesList):
        self.fileName = fileName
        self.path = path
        self.placesList = placesList
    
    def exportToExcel(self):
        writeBook= xlwt.Workbook(encoding='utf-8')
        sheet = writeBook.add_sheet("document",cell_overwrite_ok=True)
        style = xlwt.XFStyle()

        sheet.write(0, 0, 'KEYWORD')
        sheet.write(0, 1, 'NAME')
        sheet.write(0, 2, 'CATEGORY')
        sheet.write(0, 3, 'DIRECTION')
        sheet.write(0, 4, 'PHONE')
        sheet.write(0, 5, 'WEB')
        sheet.write(0, 6, 'PLUS CODE')
        sheet.write(0, 7, 'OPEN HOURS')
        sheet.write(0, 8, 'STARS')
        sheet.write(0, 9, 'REVIEWS')

        cont=1
        for place in self.placesList:
            sheet.write(cont, 0, place.keyword)
            sheet.write(cont, 1, place.name)
            sheet.write(cont, 2, place.category)
            sheet.write(cont, 3, place.address)
            sheet.write(cont, 4, place.phone)
            sheet.write(cont, 5, place.web)
            sheet.write(cont, 6, place.pluscode)
            sheet.write(cont, 7, place.open_hours)
            sheet.write(cont, 8, place.stars)
            sheet.write(cont, 9, place.reviews)
            cont = cont + 1

        writeBook.save(self.path+self.fileName)