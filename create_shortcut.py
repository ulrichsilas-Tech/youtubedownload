import plistlib
import zipfile
import io

API_URL = "https://youtubedownload-ftpc.onrender.com"

WFWorkflowActions = [
    # 1. Ask for Input (YouTube URL)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "WFAskActionPrompt": {
                "Value": {"Type": "String", "Value": "Paste YouTube URL"},
                "WFParameterKey": "WFAskActionPrompt"
            },
            "WFAskActionType": "URL",
        }
    },
    # 2. URL (API endpoint)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.url",
        "WFWorkflowActionParameters": {
            "WFURLActionURL": API_URL + "/download",
        }
    },
    # 3. Get Contents of URL (POST - request the download)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "URL"}, "WFParameterKey": "WFInput"},
            "WFHTTPMethod": "POST",
            "WFHTTPBodyType": "JSON",
            "WFRequestBody": {
                "Value": {
                    "WFSerializationType": "WFDictionaryPacker",
                    "Value": [
                        {
                            "WFKey": "url",
                            "WFValue": {"Value": {"Type": "Variable", "Variable": "Ask for Input"}, "WFParameterKey": "WFInput"}
                        },
                        {"WFKey": "format", "WFValue": "mp3"},
                        {"WFKey": "quality", "WFValue": "192"}
                    ]
                }
            },
            "ShowProcedureOutput": False,
        }
    },
    # 4. Get Dictionary Value (download_url → absolute URL)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.getdictionaryvalue",
        "WFWorkflowActionParameters": {
            "WFGetDictionaryValueKey": "download_url",
            "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}, "WFParameterKey": "WFInput"},
        }
    },
    # 5. Get Contents of URL (GET - actual file download)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "Dictionary Value"}, "WFParameterKey": "WFInput"},
            "ShowProcedureOutput": False,
        }
    },
    # 6. Save File (ask where → pick On My iPhone > Downloads)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.savefile",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}, "WFParameterKey": "WFInput"},
            "WFSaveFileAskWhere": True,
        }
    },
]

WFWorkflow = {
    "WFWorkflowMinimumClientVersionString": "1145.10",
    "WFWorkflowMinimumClientVersion": 1145,
    "WFWorkflowClientVersion": "1245.10",
    "WFWorkflowClientReleaseVersion": "1.0.0",
    "WFWorkflowIcon": {
        "WFWorkflowIconStartColor": 4282601983,
        "WFWorkflowIconGlyphNumber": 59760,
    },
    "WFWorkflowActions": WFWorkflowActions,
    "WFWorkflowTypes": ["NCWidget", "WatchKit"],
    "WFWorkflowHasShortcutInputVariables": True,
    "WFWorkflowInputContentItemClasses": ["WFURLContentItem"],
    "WFWorkflowOutputContentItemClasses": ["WFMediaContentItem", "WFFileContentItem"],
}

plist_buffer = io.BytesIO()
plistlib.dump(WFWorkflow, plist_buffer, fmt=plistlib.FMT_BINARY)

output_path = "YouTube_Downloader.shortcut"
with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("shortcut.plist", plist_buffer.getvalue())

print(f"Created: {output_path}")