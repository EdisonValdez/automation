# -*- coding: utf-8 -*-


from .data_exporter import ExportMapsData
from maps_data_scraper import GoogleMapsDataScraper
from threading import Thread
import sys
import os

def split_list(a, n):
    k, m = divmod(len(a), n)
    return list((a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n)))

def scrapeMaps(language, list, outputFolder, results, thread):
    scraper = GoogleMapsDataScraper(language, outputFolder)
    scraper.initDriver()
    placesList = []

    cont=1
    for l in list:
        place = scraper.scrapearDatos(l)
        
        if(place != None):
            print('Hilo nº '+str(thread)+' ' +str(cont) + '/' + str(len(list)) + ' - OK - ' + l)
            placesList.append(place)
        else:
            print('thread nº '+str(thread)+' ' +str(cont) + '/' + str(len(lista)) + ' - ERROR - ' + l)
        cont +=1
    
    results[thread] = placesList
def mainGoogleMaps(language, ficheroKw, outputFolder):
    archivo = open(ficheroKw,'r', encoding='utf-8')
    listaF = archivo.read().splitlines()
    archivo.close()

    threads = 5
    listaHilos = [None] * threads
    listaresults = [None] * threads
    divididos = split_list(listaF, threads)

    for i in range(len(listaHilos)):
        listaHilos[i] = Thread(target = scrapeMaps, args=(language, divididos[i], outputFolder, listaresults, i,))
        listaHilos[i].start()

    for i in range(len(listaHilos)):
        listaHilos[i].join()

    listaFinal = []

    for i in range(len(listaresults)):
        listaFinal = listaFinal + listaresults[i]

    exportar = ExportarDatosMaps(outputFolder+'00_output.xls','', listaFinal)
    exportar.exportarExcel()

if __name__ == "__main__":
    while True:
        language = input('----------\n[1] Introduce the language, (ES o EN): ')
        if(language != 'ES' and language != 'EN'):
            print("----------\n** Error ** That is not a valid language. Enter a valid language\n")
            continue
        else:
            break
    
    while True:
        fichero = input('----------\n[2] Introduce the path to save the images: ')
        if(os.path.isdir(fichero) == False):
            print("----------\n** Error ** That is not a valid folder. Enter a valid folder\n")
            continue
        else:
            caracter = fichero[len(fichero)-1]
            if(caracter != '/' or caracter != '\\'):
                fichero = fichero.replace('/','\\')+'\\'
            break
    
    while True:
        kwLugares = input('----------\n[3] Introduce the path of the keywords txt file: ')
        if(os.path.isfile(kwLugares) == False):
            print("----------\n** Error ** That is not a valid txt file. Enter a valid file\n")
            continue
        else:
            break
    
    mainGoogleMaps(language,kwLugares, fichero)