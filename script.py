#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import csv
from math import radians, cos, sin, atan2, sqrt
import urllib
import xml.etree.ElementTree as ET
import unicodedata
import os
import codecs
import string

utf8Writer = codecs.getwriter('utf8')
sys.stdout = utf8Writer(sys.stdout)

def normalize(s): return unicodedata.normalize('NFKD', unicode(s)).encode("ascii", "ignore").lower()

def calculaExpressioBooleana(consulta):
    if isinstance(consulta, basestring): return "'%s' in str" % normalize(consulta)
    elif len(consulta) > 0:
        operador = "and" if isinstance(consulta, tuple) else "or"
        expressio = "("
        primer = True
        for elem in consulta:
            if primer: primer = False
            else: expressio += " %s " % operador
            expressio += calculaExpressioBooleana(elem)
        return expressio + ")"
    else: return "(True)"


class Consulta:
    'Representa una consulta'
    def __init__(self, consulta):
        self.expressioBooleana = calculaExpressioBooleana(unicode(consulta, 'utf-8'))

    def compleixConsulta(self, str):
        return eval(self.expressioBooleana)

def parsejaParametres():
    if len(sys.argv) < 3:
        print "Usage: %s consulta transport" % sys.argv[0]
        sys.exit()
    else: 
        try:
            return (Consulta(eval(sys.argv[1])), eval(sys.argv[2]))
        except:
            print u"Els paràmetres no tenen un format correcte"
            sys.exit()

class Posicio:
    'Representa una posició en format (Latitud, Longitud)'

    RADI_TERRA = 6371000

    def __init__(self, latitud, longitud):
        self.latitud, self.longitud = map(radians, (float(latitud), float(longitud)))

    # En metres
    def distancia(self, altra):
         dlon = self.longitud - altra.longitud
         dlat = self.latitud  - altra.latitud

         a = sin(dlat/2)**2 + cos(altra.longitud)*cos(self.longitud)*sin(dlon/2)**2
         c = 2*atan2(sqrt(a), sqrt(1 - a))

         return Posicio.RADI_TERRA*c

class ParadaTransport:
    'Representa una parada de transport qualsevol, sigui Bus, FGC, Metro o Tramvia'

    TREN_SUBTERRANI, BUS_DIURN, BUS_NOCTURN, TRAMVIA = (1,2,3,4)

    def __init__(self, posicio, tipus, nom):
        def parsejaTipus(strTipus):
            inicial = strTipus[0]

            if   inicial == 'D': return ParadaTransport.BUS_DIURN
            elif inicial == 'N': return ParadaTransport.BUS_NOCTURN
            elif inicial == 'T': return ParadaTransport.TRAMVIA
            elif inicial == 'U': return ParadaTransport.TREN_SUBTERRANI

        self.tipus, self.posicio, self.nom = (parsejaTipus(tipus), posicio, nom)

    def mateixaLinia(self, altra):
        if self.tipus != altra.tipus: return False

        if self.tipus == ParadaTransport.TREN_SUBTERRANI:
            indexParentesiTancat = self.nom.index(")")
            return self.nom[:indexParentesiTancat].lower() == altra.nom[:indexParentesiTancat].lower()
        elif self.tipus == ParadaTransport.BUS_DIURN or self.tipus == ParadaTransport.BUS_NOCTURN: return self.nom == altra.nom 
        else:
            if "TRAMVIA BLAU" in self.nom != "TRAMVIA_BLAU" in altra.nom: return False
            elif "TRAMVIA_BLAU" in self.nom: return True
            else:
                indexParentesiTancat = self.nom.index(")")
                return self.nom[:indexParentesiTancat].lower() == altra.nom[:indexParentesiTancat].lower()


class ParadaBicing:
    'Representa una parada de Bicing'

    def __init__(self, posicio, carrer, numero, bicis, slots):
        self.posicio, self.carrer, self.numero, self.bicis, self.slots = (posicio, carrer, numero, bicis, slots)

    def teNumero(self): return self.numero != None

class Esdeveniment:
    'Representa un esdeveniment qualsevol'

    def __init__(self, nom, data, nom_lloc, municipi, barri, carrer, numero, codi_postal, posicio):
        self.nom, self.data, self.nom_lloc, self.municipi, self.barri, self.carrer, self.numero, self.codi_postal, self.posicio = \
         (nom, data, nom_lloc, municipi, barri, carrer, numero, codi_postal, posicio)

    def obtenirStringCerca(self):
        return normalize(self.nom + " " + self.municipi + " " + self.barri + 
            " " + self.carrer + " " + self.numero + " " + self.codi_postal)

    def obtenirAdreca(self): return self.carrer + u" nº " + self.numero + " " + self.codi_postal + " " + self.barri + " " + self.municipi


def obtenirParadesTransports():
    PATH_ESTACIONS_BUS = "./ESTACIONS_BUS.csv"
    PATH_TRANSPORTS    = "./TRANSPORTS.csv"

    DELIMITADOR = ';'

    TITOLS = ("LONGITUD", "LATITUD", "EQUIPAMENT", "NOM_CAPA_ANG")

    paradesTransports = []

    def llegeixCsv(cami):
        with open(cami, 'rb') as contingutCsv:
            lector = csv.reader(contingutCsv, delimiter=DELIMITADOR)
            
            titols = lector.next()
            index_longitud, index_latitud, index_nom, index_tipus = map(lambda t: titols.index(t), TITOLS)

            for fila in lector: 
                paradesTransports.append(ParadaTransport(Posicio(fila[index_latitud], fila[index_longitud]), fila[index_tipus], unicode(fila[index_nom], 'latin-1')))

    llegeixCsv(PATH_TRANSPORTS); llegeixCsv(PATH_ESTACIONS_BUS)

    return paradesTransports

def obtenirArbreXml(url):
    try:
        fitxerXml = urllib.urlopen(url)
    except:
        print u"No estàs connectat a Internet o el recurs " + url.encode('utf-8') + u" no està disponible"
        sys.exit()

    xmlString = fitxerXml.read()
    fitxerXml.close()

    return ET.fromstring(xmlString)

def obtenirParadesBicing():
    URL_INFO_BICING = "http://wservice.viabicing.cat/getstations.php?v=1"

    TAGS = ("lat", "long", "street", "streetNumber", "bikes", "slots", "status")

    ESTAT_OBERTA = "OPN"

    arbreXml = obtenirArbreXml(URL_INFO_BICING)

    if arbreXml == None: return []

    paradesBicing = []
    for i in range(1, len(arbreXml)):
        estacio = arbreXml[i]
        latitud, longitud, carrer, numero, bicis, slots, estat = map(lambda x: estacio.findtext(x), TAGS)

        if estat == ESTAT_OBERTA and (int(bicis) > 0 or int(slots) > 0):
            paradesBicing.append(ParadaBicing(Posicio(latitud, longitud), carrer, numero, bicis, slots))

    return paradesBicing

def obtenirEsdeveniments():
    URL_INFO_ESDEVENIMENTS = "http://w10.bcn.es/APPS/asiasiacache/peticioXmlAsia?id=199"

    TAG_ERROR = "error"
    TAG_ACTES = "body/resultat/actes"
    PATH_ADRECA = "lloc_simple/adreca_simple/"
    PATH_COORDENADES = PATH_ADRECA + "coordenades/googleMaps"
    ATTR_LATITUD = "lat"
    ATTR_LONGITUD = "lon"
    TAGS = ("nom", "data/data_proper_acte", "lloc_simple/nom", 
            PATH_ADRECA+"municipi", PATH_ADRECA+"carrer", PATH_ADRECA+"numero", 
            PATH_ADRECA+"barri", PATH_ADRECA+"codi_postal")

    arbreXml = obtenirArbreXml(URL_INFO_ESDEVENIMENTS)

    if arbreXml == None or arbreXml.find(TAG_ERROR) != None: return []
    else:
        actes = arbreXml.find(TAG_ACTES)
        if actes == None: return []
        esdeveniments = []

        for tagEsdeveniment in arbreXml.find(TAG_ACTES):
            try:
                nom, data, nom_lloc, municipi, carrer, numero, barri, codi_postal = map(lambda x: tagEsdeveniment.findtext(x), TAGS)
                tagCoordenades = tagEsdeveniment.find(PATH_COORDENADES)
                posicio = Posicio(tagCoordenades.attrib[ATTR_LATITUD], tagCoordenades.attrib[ATTR_LONGITUD])
                esdeveniment = Esdeveniment(nom, data, nom_lloc, municipi, barri, carrer, numero, codi_postal, posicio)
                if consulta.compleixConsulta(esdeveniment.obtenirStringCerca()): esdeveniments.append(esdeveniment)
            except: continue
        
        return esdeveniments

def obtenirComAnar(posicio):
    def millor(x,y): return x.posicio.distancia(posicio) < y.posicio.distancia(posicio)

    def inserirOrdenada(L, x, compare=lambda x, y: x < y):
        i = len(L)
        L.append(x)

        while i > 0 and compare(x, L[i-1]):
            L[i] = L[i-1]
            i -= 1

        L[i] = x


    def obtenirTransport(): 
        parades = []

        def seleccionaParadaIntercanviable():
            contadorDiurns = contadorNocturns = contadorSubterranis = 0
            maximDiurns = maximNocturns = maximSubterranis = maximTramvia = (-1, -1)

            for i in xrange(len(parades)):
                parada = parades[i]
                if parada.tipus == ParadaTransport.TRAMVIA:
                    dist = parada.posicio.distancia(posicio)
                    if maximTramvia[1] < dist: maximTramvia = (i, dist)
                elif parada.tipus == ParadaTransport.BUS_DIURN:
                    contadorDiurns += 1
                    dist = parada.posicio.distancia(posicio)
                    if maximDiurns[1] < dist: maximDiurns = (i, dist)
                elif parada.tipus == ParadaTransport.BUS_NOCTURN:
                    contadorNocturns += 1
                    dist = parada.posicio.distancia(posicio)
                    if maximNocturns[1] < dist: maximNocturns = (i, dist)
                else:
                    contadorSubterranis += 1
                    dist = parada.posicio.distancia(posicio)
                    if maximSubterranis[1] < dist: maximSubterranis = (i, dist)

            llista = []

            if contadorDiurns > 1: llista.append(maximDiurns)
            if contadorNocturns > 1: llista.append(maximNocturns)
            if contadorSubterranis > 1: llista.append(maximSubterranis)
            if maximTramvia[0] != -1: llista.append(maximTramvia)

            maxim = llista[0]
            for i in range(1, len(llista)):
                elem = llista[i]
                if elem[1] > maxim[1]: maxim = elem

            return maxim[0]


        def capAmbMateixaLinia(parada):
            for p in parades:
                if p.mateixaLinia(parada): return False
            return True

        hihaBusDiurn = hihaBusNocturn = hihaTrenSubterrani = False

        for parada in paradesTransports:
            if parada.posicio.distancia(posicio) <= 500 and capAmbMateixaLinia(parada):
                if len(parades) < 6: 
                    inserirOrdenada(parades, parada, millor)
                    if parada.tipus == ParadaTransport.BUS_DIURN: hihaBusDiurn = True
                    elif parada.tipus == ParadaTransport.BUS_NOCTURN: hihaBusNocturn = True
                    elif parada.tipus == ParadaTransport.TREN_SUBTERRANI: hihaTrenSubterrani = True
                elif (not hihaBusDiurn and parada.tipus == ParadaTransport.BUS_DIURN) or\
                     (not hihaBusNocturn and parada.tipus == ParadaTransport.BUS_NOCTURN) or\
                     (not hihaTrenSubterrani and parada.tipus == ParadaTransport.TREN_SUBTERRANI) or\
                     millor(parada, parades[seleccionaParadaIntercanviable()]):
                        del parades[seleccionaParadaIntercanviable()]
                        inserirOrdenada(parades, parada, millor)
                        if parada.tipus == ParadaTransport.BUS_DIURN: hihaBusDiurn = True
                        elif parada.tipus == ParadaTransport.BUS_NOCTURN: hihaBusNocturn = True
                        elif parada.tipus == ParadaTransport.TREN_SUBTERRANI: hihaTrenSubterrani = True

        if len(parades) == 0: return None
        else:
            res = "<b>Parades de transport:</b><ul>"
            for parada in parades:
                res += "<li>" + parada.nom + "</li>" 
            res += "</ul>"
            return res


    def obtenirBicing():
        paradesAmbBicis = []
        paradesAmbSlots = []

        def intentaAfegirParada(L, p):
            if len(L) < 5: 
                inserirOrdenada(L, p, millor)
            elif millor(p, L[4]):
                L.pop()
                inserirOrdenada(L, p, millor)

        def escriuParades(L, nonia, atributGetter, atributString):
            resultat = ""
            if not nonia:
                resultat += "<ul>"
                for parada in L:
                    resultat += "<li>" + parada.carrer +\
                        (u" nº " + parada.numero if parada.teNumero() else "s/n") + \
                        ", " + atributGetter(parada) + " " + atributString +\
                        u", Distància: " + str(round(parada.posicio.distancia(posicio), 2)) + "m" "</li>"
                resultat += "</ul>"
            else: resultat += "No n'hi ha"
            return resultat

        for paradaBicing in paradesBicing:
            if paradaBicing.posicio.distancia(posicio) <= 500:
                if paradaBicing.bicis > 0: intentaAfegirParada(paradesAmbBicis, paradaBicing)
                if paradaBicing.slots > 0: intentaAfegirParada(paradesAmbSlots, paradaBicing)

        senseParadesAmbBicis = len(paradesAmbBicis) == 0
        senseParadesAmbSlots = len(paradesAmbSlots) == 0
        if senseParadesAmbBicis and senseParadesAmbSlots: return None
        else:
            resultat = "<b>Parades amb bicis:</b><br/>"
            resultat += escriuParades(paradesAmbBicis, senseParadesAmbBicis, lambda x: x.bicis, "bicis")
            resultat += "<br/><b>Parades amb slots lliures:</b>"
            resultat += escriuParades(paradesAmbSlots, senseParadesAmbSlots, lambda x: x.slots, "slots lliures")
            return resultat
            



    if TRANSPORT in comAnar and (BICING not in comAnar or comAnar.index(TRANSPORT) < comAnar.index(BICING)):
        transport = obtenirTransport()
        if transport != None: return transport
        elif BICING in comAnar:
            bicing = obtenirBicing()
            if bicing != None: return bicing
    else:
        bicing = obtenirBicing()
        if bicing != None: return bicing
        elif TRANSPORT in comAnar:
            transport = obtenirTransport()
            if transport != None: return transport

    return "No se n'ha trobat"


def generarHtml():
    SENSE_DATA = "31/12/9999 00.00"

    if TRANSPORT not in comAnar and BICING not in comAnar:
        headerTransport = ""
        showTransport = False
    else: 
        headerTransport = "<th>Transport</th>"
        showTransport = True

    headerString = "<tr><th>Acte</th><th>Data</th><th>Lloc</th><th>Adreça</th>" + headerTransport + "</tr>"
    bodyString = ""
    for esdeveniment in esdeveniments:
        bodyString += "<tr><td>" + esdeveniment.nom + "</td><td>" + (esdeveniment.data if esdeveniment.data != SENSE_DATA else "Sense data") +\
        "</td><td>" + esdeveniment.nom_lloc + "</td><td>" + esdeveniment.obtenirAdreca()\
        + "</td><td>" + (obtenirComAnar(esdeveniment.posicio) if showTransport else "") + "</td></tr>"

    origFileName = fileName = "activitats_bcn"
    i = 1
    while os.path.exists(fileName + ".html"):
        fileName = origFileName + "(%d)" % i
        i += 1

    with open(fileName + ".html", "w+") as f:
        f.write("<!DOCTYPE html><html><head><title>Activitats BCN</title>\
           <meta http-equiv=Content-Type content=\"text/html; charset=utf-8\">\
           <style>.sp{color:#34495E;}h2{font-family:Arial;}table{font-family:Arial;border:1px solid #999;empty-cells:show;\
           border-collapse:collapse;border-spacing:0}table td,table th{border-left:1px solid #999;\
           border-width:0 0 0 1px;font-size:inherit;margin:0;overflow:visible;padding:.5em 1em}\
           table td{background-color:#fff}tbody tr td:first-child{font-weight:700}\
           thead{background-color:#34495E;color:#fff;text-align:left}\
           tbody tr:nth-child(even) td{background-color:#e2e2e2}</style>\
           <body><h2><b>Consulta:</b> <span class='sp'>" + sys.argv[1] + "</span></h2><h2><b>Com anar-hi:</b>\
           <span class='sp'>" + sys.argv[2] + "</span></h2><table><thead>" + headerString + "</thead><tbody>" + bodyString.encode('utf-8') + "</tbody></table>")

TRANSPORT = "transport"
BICING    = "bicing"

consulta, comAnar = parsejaParametres()

print "Carregant formes de transport..."
if TRANSPORT in comAnar: paradesTransports = obtenirParadesTransports()
if BICING in comAnar:    paradesBicing     = obtenirParadesBicing()

print "Baixant esdeveniments..."
esdeveniments        = obtenirEsdeveniments()

print "Generant fitxer HTML..."
generarHtml()
