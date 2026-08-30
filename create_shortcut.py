import plistlib
import zipfile
import io

API_URL = "https://youtubedownload-ftpc.onrender.com"

WFWorkflowActions = [
    # 1. Ask for Input
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "WFAskActionPrompt": {
                "Value": {"Type": "String", "Value": "Paste YouTube URL"},
                "WFParameterKey": "WFAskActionPrompt"
            },
            "WFAskActionType": "URL",
            "WFInput": "",
        }
    },
    # 2. URL - build endpoint
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.url",
        "WFWorkflowActionParameters": {
            "WFURLActionURL": API_URL + "/download",
        }
    },
    # 3. Dictionary - build JSON body
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
        "WFWorkflowActionParameters": {
            "WFItems": {
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
            }
        }
    },
    # 4. Get Contents of URL (POST)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "URL"}},
            "WFHTTPMethod": "POST",
            "WFHTTPHeaders": [
                {
                    "WFHeaderFieldType": "Header Field",
                    "WFHeaderValue": "application/json",
                    "WFHeaderFieldName": "Content-Type"
                }
            ],
            "WFHTTPBodyType": "JSON",
            "WFRequestBody": {"Value": {"Type": "Variable", "Variable": "Dictionary"}},
            "ShowProcedureOutput": False,
        }
    },
    # 5. Get Dictionary Value - download_url
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.getdictionaryvalue",
        "WFWorkflowActionParameters": {
            "WFGetDictionaryValueKey": "download_url",
            "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}},
        }
    },
    # 6. URL - build full download link
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.url",
        "WFWorkflowActionParameters": {
            "WFURLActionURL": API_URL + "{0}",
        }
    },
    # 7. Get Contents of URL (GET file)
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "URL"}},
            "ShowProcedureOutput": False,
        }
    },
    # 8. Save File
    {
        "WFWorkflowActionIdentifier": "is.workflow.actions.savefile",
        "WFWorkflowActionParameters": {
            "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}},
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

# Write plist to memory
plist_buffer = io.BytesIO()
plistlib.dump(WFWorkflow, plist_buffer, fmt=plistlib.FMT_BINARY)

# Create shortcut as a zip file (zip method - works on newer iOS)
output_path = "YouTube_Downloader.shortcut"
with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("shortcut.plist", plist_buffer.getvalue())

print(f"Created: {output_path}")