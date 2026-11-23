import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

ids = [
    'backendStatus', 'backendStatusText', 'samplePicker', 'sessionIdBadge',
    'btnLoadSession', 'loadSpinner', 'instructionInput', 'btnSendInstruction',
    'responseFeed', 'historyCount', 'wordStream', 'timelineDurationText',
    'timelineWordCount', 'timelineHashBadge', 'btnRender', 'progressSection',
    'progressBarFill', 'progressStatusText', 'progressPercentText', 'videoPlayer',
    'videoPlaceholder', 'exportTray', 'downloadVideoBtn', 'downloadOtioBtn',
    'btnViewManifest', 'btnViewTimeline', 'jsonModal', 'modalTitle',
    'modalJsonContent', 'modalCloseBtn', 'tabSampleBtn', 'tabUrlBtn',
    'tabUploadBtn', 'tabUrlContent', 'tabUploadContent', 'customUrlInput',
    'fileUploadInput'
]

missing = [i for i in ids if f'id="{i}"' not in html and f"id='{i}'" not in html]
if missing:
    print('Missing IDs:', missing)
else:
    print('SUCCESS: All 37 DOM IDs used in app.js exist in static/index.html!')
