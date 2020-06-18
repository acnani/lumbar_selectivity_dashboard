import dash
import dash_core_components as dcc
import dash_html_components as html
import utils.dash_reusable_components as drc
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import numpy as np
import base64
import pandas as pd
import urllib
import publicHelper as hf
import os

client = hf.client
db = hf.db
collection = hf.collection

app = dash.Dash(__name__)
app.config['suppress_callback_exceptions']=True
app.title = 'Lumbar Selectivity Viewer'
server = app.server

dataDF = pd.DataFrame()

anonymizedList = {'Cat E':'Electro',
                  'Cat F':'Freeze',
                  'Cat G':'Galactus',
                  'Cat H':'Hobgoblin',
                  'Cat I':'HA02',
                  'Cat J':'HA04',}

app.layout = html.Div(children=[
    # .container class is fixed, .container.scalable is scalable
    html.Div(className="banner", children=[
        # Change App Name here
        html.Div(className='container scalable', children=[
            # Change App Name here
            html.H2(html.A('Lumbar DRG selectivity viewer',
                # href='https://github.com/plotly/dash-svm',
                style={
                    'text-decoration': 'none',
                    'color': 'inherit'
                }
            )),
            html.Div(
                html.A(
                    html.Img(
                        src='data:image/png;base64,{}'.format(base64.b64encode(open(os.path.join("RNEL_logo.png"),'rb').read())),height="100%",),
                    href='http://www.rnel.pitt.edu/', target='_blank'
                ),
            style={"float": "right", "height": "70%",})
        ]),
    ]),

        html.Div(
                className='three columns',
                children=[
                    drc.Card([

                        drc.NamedDropdown(
                            name='Select Electrode: ',
                            id='dropdown-select-eType',
                            options=[
                                {'label': 'epineural', 'value': 'epineural'},
                                {'label': 'penetrating', 'value': 'penetrating'},
                            ],
                            value='epineural',
                            clearable=False,
                            searchable=False,
                        ),


                        drc.NamedDropdown(
                            name='Select Subject: ',
                            id='dropdown-select-subject',
                            options=[
                            ],
                            clearable=False,
                            searchable=False,
                            # value='moons'
                        ),

                        drc.NamedDropdown(
                            name='Select Session: ',
                            id='dropdown-select-session',
                            options=[{}],
                            clearable=False,
                            searchable=False,
                        ),

                        drc.NamedDropdown(
                            name='Select Stim channel: ',
                            id='dropdown-select-stimChan',
                            options=[{}],
                            clearable=False,
                            searchable=False,
                        ),

                        drc.NamedDropdown(
                            name='Select Stim amp: ',
                            id='dropdown-select-stimAmp',
                            options=[{}],
                            clearable=False,
                            searchable=False,
                        ),

                        html.A("Download CSV",
                               id='download_link',
                               download="rawdata.csv",
                               href="",
                               target="_blank"
                               ),
                    ]),
                    drc.Card(['Select the desired trial of DRG stimulation from the dropdown menus above. The graph on the top right will '
                              'display the stimulus triggered average (STA) electroneurogram (ENG) recorded at distal nerve branches of the sciatic and femoral nerve. '
                              'The graph below will display an innervation tree where each node represents a nerve. The color of each node '
                              'represents the minimum stimulation amplitude (or activation threshold) that produced a compound action potential (CAP) for the selected stimulation channel. '
                              'Hover over each node for nerve identity and threshold. You can also download the data for each trial as a CSV file.']),
                ]
            ),
    html.Div(
        className='nine columns',
        children=[
            drc.Card([
                html.Div(
                    id='div-graphs',
                    children=dcc.Graph(
                        id='STA_ENG',
                    )
                ),
            ]),

            drc.Card([
                html.Div(
                    id='div-graphs2',
                    children=dcc.Graph(
                        id='innervationTree',
                        style={"height": "33vh"},
                    )
                ),
            ]),
        ]),
])


@app.callback (Output('dropdown-select-subject', "options"),
               [Input('dropdown-select-eType', 'value')],)
def getSubs(eTypeVal):
    subList = []
    if eTypeVal == 'epineural':
        subList =  ['Cat G','Cat H','Cat I','Cat J']
    elif eTypeVal == 'penetrating':
        subList =  ['Cat E','Cat F','Cat G','Cat H']
    
    return [{'label': iSub, 'value': anonymizedList[iSub]} for iSub in subList]

@app.callback (Output('dropdown-select-subject', "value"),
               [Input('dropdown-select-eType', 'value')],)
def getSubVal(subjVal):
    return ''


@app.callback (Output('dropdown-select-session', "options"),
               [Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getSesh(subjVal, eTypeVal):
    seshDrop = []
    if subjVal:
        seshList = []
        if eTypeVal == 'epineural':
            seshList =  hf.epineuralSessions[subjVal]
        elif eTypeVal == 'penetrating':
            seshList =  hf.penetratingSessions[subjVal]
        seshDrop = []
        for iSesh in sorted(seshList):
            iDRG = db[collection].find({'subject':subjVal,'session':iSesh}).distinct('DRG')
            seshDrop.append({'label': 'session %d (%s)'%(iSesh, iDRG[0]), 'value': iSesh})

    return seshDrop

@app.callback (Output('dropdown-select-session', "value"),
               [Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getSeshVal(subjVal, eTypeVal):
    return ''


@app.callback (Output('dropdown-select-stimChan', "options"),
               [Input('dropdown-select-session', "value"),
                Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getStimChan(seshVal, subjVal, eTypeVal):
    chanList = sorted(list(db[collection].find({'subject':subjVal,
                           'session': seshVal}).distinct('stimChan')))
    return [{'label': iChan, 'value': iChan} for iChan in chanList]

@app.callback (Output('dropdown-select-stimChan', "value"),
               [Input('dropdown-select-session', "value"),
                Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getStimChanVal(seshVal, subjVal, eTypeVal):
    return ''


@app.callback (Output('dropdown-select-stimAmp', "options"),
               [Input('dropdown-select-stimChan', "value"),
                Input('dropdown-select-session', "value"),
                Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getStimAmp(stimChan, seshVal, subjVal, eTypeVal):
    ampList = sorted(list(db[collection].find({'subject':subjVal,
                                                     'stimChan': stimChan,
                                          'session': seshVal}).distinct('amplitude')))

    return [{'label': round(iAmp,2), 'value': round(iAmp,2)} for iAmp in ampList]

@app.callback (Output('dropdown-select-stimAmp', "value"),
               [Input('dropdown-select-stimChan', "value"),
                Input('dropdown-select-session', "value"),
                Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getAmpVal(stimChan, seshVal, subjVal, eTypeVal):
    return ''


@app.callback (Output('STA_ENG', "figure"),
               [Input('dropdown-select-stimAmp', "value"),
                Input('dropdown-select-stimChan', "value"),
                Input('dropdown-select-session', "value"),
               Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def getSTAENGsnips(amp, stimChan, sesh, subj, eTypeVal):

    if amp:
        engObj = list(db[collection].find({'subject': subj,
                                                 'session': sesh,
                                                 'amplitude': {"$lte": amp + 0.1, "$gte": amp - 0.1},
                                                 'stimChan': stimChan}))

        engObj_sorted = [loc for x in hf.ENG_graphOrder for loc in engObj if loc['location'] == x]

        figData = []
        global dataDF
        dataDF = pd.DataFrame()
        for iObj in engObj_sorted:
            yENG = iObj['wf']
            numSamples = len(yENG)
            xtime = list(np.linspace(0, float(numSamples) / 30, numSamples))
            figData.append(go.Scatter(
                x=xtime,
                y=yENG,
                mode='lines',
                line=dict(shape='spline'),
                name = iObj['location'],
                hoverinfo = 'none'
            ))

            dataDF[iObj['location']] = yENG

        dataDF['time (ms)'] = xtime
        layout = dict(margin=dict(l=60, r=10, t=0, b=70),  legend=dict(yanchor="bottom",y=0),
                      xaxis=dict(title='Time (ms)'),
                      yaxis=dict(fixedrange=True, title='amp (uV)'))

        return dict(data=figData, layout=layout)
    else:
        return dict(data=[], layout=[])

@app.callback (Output('innervationTree', "figure"),
               [Input('dropdown-select-stimChan', "value"),
                Input('dropdown-select-session', "value"),
                Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def createInnervationTreeDiagram(chan, session, subject, eTypeVal):
    if chan:
        allThreshDict = hf.thresholdPerCuff(subject, session, chan, ['BiFem'], True)
        if chan in allThreshDict.keys():
            threshDict = allThreshDict[chan]
            resultCuffs = threshDict.keys()
            allAmps = [threshDict[cuffName] for cuffName in resultCuffs]
            tmp = hf.generateInnervationTree(resultCuffs, allAmps, 25)
            tmp['layout']['title'] = tmp['layout']['title'] + ' (hover for activation threshold) '
            tmp['layout']['margin'] = dict(t=30, b=20)
            return tmp
        else:
            return dict(data=[], layout=[])
    else:
        return dict(data=[], layout=[])


@app.callback (Output('download_link', "download"),
               [Input('dropdown-select-stimAmp', "value"),
                Input('dropdown-select-stimChan', "value"),
                Input('dropdown-select-session', "value"),
               Input('dropdown-select-subject', 'value'),
                Input('dropdown-select-eType', 'value')],)
def setFileName(amp, stimChan, sesh, subj, eTypeVal):
    if amp:
        return '%s_ssn%03d_chan%02d_amp%0.2f_%s.csv' %(subj, sesh, stimChan, amp,eTypeVal)


@app.callback (Output('download_link', 'href'),
               [Input('download_link', "n_clicks"),
                Input('STA_ENG', "figure"),
                Input('dropdown-select-stimAmp', "value")],)
def downloadDF(n, fig, amp):
    if amp:
        global dataDF
        csv_string = dataDF.to_csv(index=False, encoding='utf-8')
        csv_string = "data:text/csv;charset=utf-8," + urllib.quote(csv_string)
        return csv_string

# Running the server
if __name__ == '__main__':
    app.run_server(debug=False)
    # app.run_server(debug=True)