import pymongo
import matplotlib
from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import collections
import plotly.graph_objs as go
from igraph import *
import os

client = pymongo.MongoClient(os.environ['SELECTIVITY_MONGO'])

db = client.acute
collection = 'selectivity'

# cuff dbName:label
allCuffs_mdf = collections.OrderedDict([('Sciatic_Proximal','Sci'),
                                        ('Tibial','Tib'),
                                        ('Lat_Gas','LG'),
                                        ('Med_Gas','MG'),
                                        ('Dist_Tib','dTib'),
                                        ('Cmn_Per','CP'),
                                        ('Dist_Cmn_Per','dCP'),
                                        ('Dist_Cmn_Per_2','dCP2'),
                                        ('L_D_Cmn_Per','SP'),
                                        ('M_D_Cmn_Per','DP'),
                                        ('BiFem','BF'),
                                        ('Sural','Sur'),
                                        ('Lat_Cut','LC'),
                                        ('Med_Cut','MC'),
                                        ('Sens_Branch','Sensory'),
                                        ('Femoral_Proximal', 'Fem'),
                                        ('Saph', 'Sph'),
                                        ('VLat', 'VL'),
                                        ('VMed', 'VM'),
                                        ('Sart', 'Srt'),
                                        ])

combineCuffs = {'Sural':'Sens_Branch',
                'Lat_Cut':'Sens_Branch',
                'Med_Cut':'Sens_Branch',
                'Sens_Branch':'Sens_Branch',
                'Dist_Cmn_Per':'Dist_Cmn_Per',
                'Dist_Cmn_Per_2':'Dist_Cmn_Per',
                'L_D_Cmn_Per':'Dist_Cmn_Per',
                'M_D_Cmn_Per':'Dist_Cmn_Per'}

PWbySession = {'Electro':{20:204.8, 22:204.8, 26:204.8, 27:204.8, 28:204.8, 32:204.8},
               'Freeze':{55:204.8, 56:204.8, 59:204.8, 60:204.8, 61:204.8, 63:204.8, 68:204.8, 999:204.8},
                'Galactus':{15:204.8, 30:81.92, 40:81.92, 41:81.92, 48:81.92, 57:81.92,
                           91:81.92, 94:81.92, 97:81.92, 98:81.92},
                'Hobgoblin':{6:81.92, 7:81.92, 10:81.92, 12:81.92, 14:81.92, 16:81.92, 20:81.92, 23:81.92,
                             47:81.92, 49:81.92, 52:81.92},
                'HA02':{2:204.8, 3:204.8, 4:204.8},
                'HA04':{2:80, 3:80, 4:80}}

epineuralSessions = {'Galactus':[15, 30, 40, 41, 48],
                     'Hobgoblin':[6, 7, 10, 12, 14, 16],
                     'HA02':[2, 3, 4],
                     'HA04':[2, 3, 4]}

penetratingSessions = {'Electro':[20, 22, 26, 27, 28, 32],
                       'Freeze':[55, 56, 59, 60, 61, 63, 999],
                       'Galactus':[91, 94, 97, 98],
                       'Hobgoblin':[47, 49, 52]}

## create heatmap colormap
def createMagmaCMAP():
    magma_cmap = matplotlib.cm.get_cmap('magma')
    magma_rgb = []
    norm = matplotlib.colors.Normalize(vmin=0, vmax=255)

    for i in range(0, 255):
        k = matplotlib.colors.colorConverter.to_rgb(magma_cmap(norm(i)))
        magma_rgb.append(k)

    h = 1.0 / (255 - 1)
    pl_colorscale = []

    for k in range(255):
        C = map(np.uint8, np.array(magma_cmap(k * h)[:3]) * 255)
        pl_colorscale.append([k * h, 'rgb' + str((C[0], C[1], C[2]))])

    return pl_colorscale
magma = createMagmaCMAP()

def convertCurrentToCharge(amplitude_uA, sub, sesh):
    return np.ceil((amplitude_uA*1e-6*PWbySession[sub][sesh]* 1e-6*1e9)*1000)/1000   # ensure 2 decimal places

# animal:DRG(session):channel(block):amp:cuff:cv
def thresholdPerCuff(sub, session, chan,ignoreCuffList, combine, stimUnits='amplitude'):
    ignoreCuffList.extend(['Sciatic_Distal','Femoral_Distal'])
    result1 = db[collection].aggregate([
            {'$match': {
                "subject": sub,
                "session": session,
                "location":{"$nin":ignoreCuffList},
                "stimChan":chan,
            }},
            {"$group": {
                "_id": {"cuff": "$location",
                        "stimChan": "$stimChan",
                        'is_sig':'$is_sig',
                        'is_sig_manual':'$is_sig_manual'},
                "threshAmp": {"$min": "$amplitude"}
            }},
            {"$project": {
                "_id": 0,
                'sig':"$_id.is_sig",
                'sig_manual':"$_id.is_sig_manual",
                "stimChan": "$_id.stimChan",
                "cuff": "$_id.cuff",
                "threshAmp": "$threshAmp",
            }}])

    res1 = list(result1)
    thresholdDict = {}
    if len(res1) != 0:
        for entry in res1:
            if ('sig_manual' in entry.keys() and entry['sig_manual'] == 1) or ('sig_manual' not in entry.keys() and entry['sig'] == 1):
                thresholdDict.setdefault(entry['stimChan'], {})
                # if not(entry['cuff'] in ['Sciatic_Distal', 'Femoral_Distal']):
                if stimUnits =='charge':
                    stimVal = convertCurrentToCharge(entry['threshAmp'],sub, session)
                else:
                    stimVal = entry['threshAmp']

                if entry['cuff'] in combineCuffs.keys():
                    if combine:
                        combinedKey = combineCuffs[entry['cuff']]
                        thresholdDict[entry['stimChan']].setdefault(combinedKey, 999)
                        tmp = [thresholdDict[entry['stimChan']][combinedKey]]
                        tmp.append(stimVal)
                        thresholdDict[entry['stimChan']][combinedKey] = min(tmp)
                    else:
                        # in case sig_manual is 1 sig is 1 is greater than sig manual =1 and sig =0, the threshold will be overwritten to a higher value
                        thresholdDict[entry['stimChan']].setdefault([entry['cuff']],999)
                        tmp = thresholdDict[entry['stimChan']][entry['cuff']]
                        thresholdDict[entry['stimChan']][entry['cuff']] = min(tmp, stimVal)
                        thresholdDict[entry['stimChan']][entry['cuff']] = stimVal
                else:
                    thresholdDict[entry['stimChan']].setdefault(entry['cuff'], 999)
                    tmp = thresholdDict[entry['stimChan']][entry['cuff']]
                    thresholdDict[entry['stimChan']][entry['cuff']] = min(tmp, stimVal)
                    # thresholdDict[entry['stimChan']][entry['cuff']] = stimVal

    return thresholdDict

## Innervation Tree related
def getInnervationParents(): # getCanonicalInnervation
    innervationDict  = {}
    innervationDict['Sciatic_Proximal']= ''
    innervationDict['Cmn_Per']= 'Sciatic_Proximal'
    innervationDict['Tibial'] = 'Sciatic_Proximal'
    innervationDict['BiFem'] = 'Sciatic_Proximal'
    innervationDict['Sural']= 'Sciatic_Proximal'
    innervationDict['Lat_Cut'] = 'Sciatic_Proximal'
    innervationDict['Med_Cut']= 'Sciatic_Proximal'
    innervationDict['Sens_Branch']= 'Sciatic_Proximal'
    innervationDict['Dist_Cmn_Per'] = 'Cmn_Per'
    innervationDict['Dist_Cmn_Per_2']= 'Cmn_Per'
    innervationDict['L_D_Cmn_Per']= 'Dist_Cmn_Per'
    innervationDict['M_D_Cmn_Per']= 'Dist_Cmn_Per'
    innervationDict['Med_Gas']= 'Tibial'
    innervationDict['Lat_Gas']= 'Tibial'
    innervationDict['Dist_Tib']= 'Tibial'
    innervationDict['Femoral_Proximal'] = ''
    innervationDict['Saph']= 'Femoral_Proximal'
    innervationDict['VMed']= 'Femoral_Proximal'
    innervationDict['VLat']= 'Femoral_Proximal'
    innervationDict['Sart'] = 'Femoral_Proximal'
    # innervationDict['Lat_Fem']= ''
    # innervationDict['Med_Fem']= ''
    # innervationDict['Mid_Fem']= ''

    return innervationDict

def getInnervationChildren():
    innervationDict  = {}
    innervationDict['Sciatic_Proximal']= ['Cmn_Per', 'Tibial', 'BiFem','Sural','Lat_Cut','Med_Cut','Sens_Branch']
    innervationDict['Cmn_Per'] = ['Dist_Cmn_Per', 'Dist_Cmn_Per_2']
    innervationDict['Dist_Cmn_Per'] = ['L_D_Cmn_Per', 'M_D_Cmn_Per']
    innervationDict['Tibial']= ['Med_Gas', 'Lat_Gas', 'Dist_Tib']
    innervationDict['Femoral_Proximal'] = ['Saph', 'VMed', 'VLat', 'Sart']
    innervationDict[''] = ['Femoral_Proximal', 'Sciatic_Proximal']


    return innervationDict

def getInnervationTreeCoords():
    coords = {}
    coords['Sciatic_Proximal'] = [3.6, 4.0]
    coords['Cmn_Per'] = [7.9, 3.0]
    coords['Tibial'] = [5.4, 3.0]
    coords['BiFem'] = [4.4, 3.0]
    coords['Sural'] = [3.4, 3.0]
    coords['Sens_Branch'] = [2.4, 3.0]
    coords['Med_Cut'] = [1.4, 3.0]
    coords['Lat_Cut'] = [0.4, 3.0]
    coords['Dist_Cmn_Per'] = [8.4, 2.0]
    coords['Dist_Cmn_Per_2'] = [7.4, 2.0]
    coords['L_D_Cmn_Per'] = [8.9, 1.0]
    coords['M_D_Cmn_Per'] = [7.9, 1.0]
    coords['Med_Gas'] = [6.4, 2.0]
    coords['Lat_Gas'] = [5.5, 2.0]
    coords['Dist_Tib'] = [4.4, 2.0]
    coords['Femoral_Proximal'] = [-2.3, 4.0]
    coords['Saph'] = [-0.8, 3.0]
    coords['VMed'] = [-1.8, 3.0]
    coords['VLat'] = [-2.8, 3.0]
    coords['Sart'] = [-3.8, 3.0]

    return coords

def generateInnervationTree(resultCuffs, nodeColor, nodeSize=40, stimUnits='amplitude', eType='epineural'):

    cuffParentsDict = getInnervationParents()
    graphEdges = []
    for cuffName in resultCuffs:
        if cuffName in cuffParentsDict.keys():
            parent = cuffParentsDict[cuffName]
            if parent != '':
                if parent in resultCuffs:
                    graphEdges.append([resultCuffs.index(parent), resultCuffs.index(cuffName)])

    cuffCoord = getInnervationTreeCoords()
    lay = [cuffCoord[iCuff] for iCuff in resultCuffs]

    G = Graph()
    G.add_vertices(len(resultCuffs))
    G.add_edges(graphEdges)
    E = [e.tuple for e in G.es]  # list of edges
    L = len(lay)
    Xn = [lay[k][0] for k in range(L)]
    Yn = [lay[k][1] for k in range(L)]
    Xe = []
    Ye = []
    for edge in E:
        Xe += [lay[edge[0]][0], lay[edge[1]][0], None]
        Ye += [lay[edge[0]][1], lay[edge[1]][1], None]

    if isinstance(nodeColor, list):
        hoverText = ['%s, c%0.1f' % (allCuffs_mdf[x], y) for x,y in zip(resultCuffs,nodeColor)]
    elif isinstance(nodeSize, list):
        hoverText = ['%s, c%0.1f' % (allCuffs_mdf[x], y) for x,y in zip(resultCuffs,nodeSize)]
    else:
        hoverText = []

    if stimUnits == 'charge':
        if eType == 'epineural':
            colorMap = [9,26]
        else:
            colorMap = [1,6] #[6, 1]
    else:                               # current
        if eType == 'epineural':
            colorMap = [300, 0]
        else:
            colorMap = [40, 0]

    lines = go.Scatter(x=Xe,
                       y=Ye,
                       mode='lines',
                       line=dict(color='rgb(210,210,210)', width=1),
                       hoverinfo='none'
                       )
    dots = go.Scatter(x=Xn,
                      y=Yn,
                      mode='markers',
                      marker=dict(size=nodeSize,
                                  color=nodeColor,  # '#DB4551',
                                  cmin=colorMap[0], cmax=colorMap[1],
                                  line=dict(color='rgb(50,50,50)', width=1),
                                  colorscale=magma,
                                  # colorscale=[[0, 'rgb(49,54,149)'],  # 0
                                  #               [0.0005, 'rgb(69,117,180)'],  # 10
                                  #               [0.005, 'rgb(116,173,209)'],  # 100
                                  #               [0.05, 'rgb(171,217,233)'],  # 1000
                                  #               [0.5, 'rgb(224,243,248)'],
                                  #               [0.75, 'rgb(215,48,39)'],# 10000
                                  #               [1.0, 'rgb(165,0,38)'],  # 100000
                                  #               ],
                                  colorbar=dict(thickness=20)
                                  ),
                      text=hoverText,
                      hoverinfo='text',
                      opacity=1
                      )

    layout = dict(title='Innervation tree',
                  font=dict(size=12),
                  showlegend=False,
                  xaxis=dict(range=[-5, 10], showline=False, zeroline=True, showgrid=False, showticklabels=False, ),
                  yaxis=dict(range=[1.5, 4.5], showline=False, zeroline=True, showgrid=True, showticklabels=False, ),
                  margin=dict(l=40, r=40, b=85, t=100),
                  hovermode='closest',
                  plot_bgcolor='rgb(248,248,248)'
                  )

    data = [lines, dots]
    fig = dict(data=data, layout=layout)

    return fig

