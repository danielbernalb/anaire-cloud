from bottle import route, run, request
import json
import sys
import requests
import json
import base64
import yaml
import time
from paho.mqtt import client as mqtt
justonce = True
interval = 5
ADMIN_LOGIN = 'admin'

#ADMIN_PASS = "${GRAFANA_ADMIN_PASSWORD}"
if (len(sys.argv) != 4):
  print('Usage: '+sys.argv[0]+' <grafana IP:port> <GRAFANA_ADMIN_PASS> <mqtt IP:port>. Found '+str(len(sys.argv))+' arguments.')
  exit()
GRAFANA_URL = sys.argv[1]
ADMIN_PASS = sys.argv[2]
MQTT_URL = sys.argv[3]

HEADERS = {'Authorization': 'Basic '+base64.b64encode((ADMIN_LOGIN+':'+ADMIN_PASS).encode('ascii')).decode('ascii'), 'Content-type': 'application/json'}
#reference dict
reference_dict = {}
client = mqtt.Client()

@route('/update')
def do_update():
    print('llega peticion')
    query = dict(request.query.decode())
    print(json.dumps(query))
    grafana_update(query)
    device_update(query)
    return "ok"

def grafana_update(update):
    print('Send mqtt message')
    
    #Update 'general' dashboard
    URL  = 'http://' + GRAFANA_URL + '/api/search?type=dash-db&tag=general'
    response = json.loads(requests.get(url=URL, headers=HEADERS).content)
    if len(response) > 0:
      uid = response[0].get('uid', None)
      if uid:
        general_dashboard_url  = 'http://' + GRAFANA_URL + '/api/dashboards/uid/' + uid
        update_summary_dashboard(update, general_dashboard_url)
        
    #Update the area dashboard
    #Find the area dashboard with the appropriate folderId
    area_dashboard_list_url = 'http://' + GRAFANA_URL + '/api/search?type=dash-db&tag=area'
    area_dashboard_list = json.loads(requests.get(url=area_dashboard_list_url, headers=HEADERS).content)
    for area_dashboard in area_dashboard_list:
      if int(area_dashboard['folderId']) == int(update['folderId']):
        area_dashboard_url  = 'http://' + GRAFANA_URL + '/api/dashboards/uid/' + area_dashboard['uid']
        update_summary_dashboard(update, area_dashboard_url)
        break
        
    #Update device dashboard
    device_dashboard_url  = 'http://' + GRAFANA_URL + '/api/dashboards/uid/' + update['db_uid']
    update_device_dashboard(update, device_dashboard_url)

def device_update(update):
    data = {
      'warning': update['warning'],
      'caution': update['caution'],
      'alarm': update['alarm']
    }
    client.publish("config/" + update['id'],json.dumps(data))

def on_publish(client,userdata,result):
  print("data published \n")
  pass

def post(URL,DATA,HEADERS):
  try:
    response = requests.post(url=URL, data=DATA,headers=HEADERS)
    return response.content
  except requests.exceptions.RequestException as e:  # This is the correct syntax
    raise SystemExit(e)

def update_summary_dashboard(sensor_info, dashboard_url):
  try:
    '''
    print('*****************')
    print('Update summary ' + dashboard_url)
    print('sensor_info: ' + yaml.safe_dump(sensor_info))
    print('*****************')
    '''
    #Get the dashboard
    area_dashboard = json.loads(requests.get(url=dashboard_url, headers=HEADERS).content)
    #Find the panel with the link to the dashboard with uid sensor_info['db_uid']
    panel = next(panel for panel in area_dashboard['dashboard']['panels'] if (panel['type'] == 'stat' and panel['links'][0]['url'].split('/')[4] == sensor_info['db_uid']))
    #Update the caution thredshold
    panel['fieldConfig']['defaults']['thresholds']['steps'][2]['value'] = sensor_info['warning']
    panel['fieldConfig']['defaults']['thresholds']['steps'][3]['value'] = sensor_info['caution']
    area_dashboard['folderId'] = area_dashboard['meta']['folderId']

    #Update the dashboard
    response = post('http://' + GRAFANA_URL + '/api/dashboards/db', json.dumps(area_dashboard),HEADERS)
  except requests.exceptions.RequestException as e:
    raise SystemExit(e)

def update_device_dashboard(sensor_info, dashboard_url):
  try:
    '''
    print('*****************')
    print('Update device ' + dashboard_url)
    print('caution: ' + yaml.safe_dump(sensor_info))
    print('*****************')
    '''
    #Get the dashboard
    device_dashboard = json.loads(requests.get(url=dashboard_url, headers=HEADERS).content)
    #Update the caution and warning thredsholds
    #print(yaml.safe_dump(device_dashboard['dashboard']['panels'][0]))
    device_dashboard['dashboard']['panels'][0]['thresholds'][0]['value'] = int(sensor_info['warning'])
    device_dashboard['dashboard']['panels'][0]['thresholds'][1]['value'] = int(sensor_info['caution'])
    if 'alert'in device_dashboard['dashboard']['panels'][0]:
      device_dashboard['dashboard']['panels'][0]['alert']['conditions'][0]['evaluator']['params'][0] = int(sensor_info['caution'])
    device_dashboard['folderId'] = device_dashboard['meta']['folderId']
    #Update the dashboard
    response = post('http://' + GRAFANA_URL + '/api/dashboards/db', json.dumps(device_dashboard),HEADERS)
  except requests.exceptions.RequestException as e:
    raise SystemExit(e)

def main():
  client.on_publish = on_publish
  client.connect(MQTT_URL.split(':')[0], int(MQTT_URL.split(':')[1]))
  client.loop_start()
  run(host='0.0.0.0', port=8080, debug=True)

if __name__ == "__main__":
  main()
