import plistlib
import struct
import io
import uuid

# Build the shortcut workflow
WFWorkflow = {
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowIcon": {
        "WFWorkflowIconStartColor": 4276895231,
        "WFWorkflowIconGlyphNumber": 59760
    },
    "WFWorkflowActions": []
}

# Action 1: Ask for Input
action1 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
    "WFWorkflowActionParameters": {
        "WFAskActionPrompt": {"Value": {"Type": "String", "Value": "YouTube URL"}, "WFParameterKey": "WFAskActionPrompt"},
        "WFAskActionType": "URL",
    }
}

# Action 2: Set Variable (URL)
action2 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "Ask for Input"}},
        "WFVariableName": "YouTubeURL",
    }
}

# Action 3: URL (construct download endpoint)
action3 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.url",
    "WFWorkflowActionParameters": {
        "WFURLActionURL": "https://youtubedownload-ftpc.onrender.com/download",
    }
}

# Action 4: Get Contents of URL (POST)
action4 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "URL"}},
        "WFHTTPMethod": "POST",
        "WFHTTPHeaders": [
            {"WFHeaderFieldType": "Header Field", "WFHeaderValue": "application/json", "WFHeaderFieldName": "Content-Type"},
        ],
        "WFHTTPBodyType": "JSON",
        "WFRequestBody": {
            "Value": {
                "WFSerializationType": "WFDictionaryPacker",
                "Value": [
                    {
                        "WFKey": "url",
                        "WFValue": {"Value": {"Type": "Variable", "Variable": "YouTubeURL"}, "WFParameterKey": "WFInput"}
                    },
                    {
                        "WFKey": "format",
                        "WFValue": "mp3"
                    },
                    {
                        "WFKey": "quality",
                        "WFValue": "192"
                    }
                ]
            }
        },
        "ShowProcedureOutput": False,
    }
}

# Action 5: Get Dictionary Value (download_url)
action5 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.getdictionaryvalue",
    "WFWorkflowActionParameters": {
        "WFGetDictionaryValueKey": "download_url",
        "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}},
    }
}

# Action 6: Set Variable
action6 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "Dictionary Value"}},
        "WFVariableName": "DownloadPath",
    }
}

# Action 7: URL (construct full download URL)
action7 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.url",
    "WFWorkflowActionParameters": {
        "WFURLActionURL": "https://youtubedownload-ftpc.onrender.com",
    }
}

# Action 8: Combine Text
action8 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.text.combine",
    "WFWorkflowActionParameters": {
        "WFTextSeparator": "",
        "WFCombineText": [
            {"Value": {"Type": "Variable", "Variable": "URL"}, "WFParameterKey": "WFInput"},
            {"Value": {"Type": "Variable", "Variable": "DownloadPath"}, "WFParameterKey": "WFInput"},
        ],
    }
}

# Action 9: Set Variable for full URL
action9 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "Combined Text"}},
        "WFVariableName": "FullDownloadURL",
    }
}

# Action 10: Get Contents of URL (download file)
action10 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "FullDownloadURL"}},
        "ShowProcedureOutput": False,
    }
}

# Action 11: Save File
action11 = {
    "WFWorkflowActionIdentifier": "is.workflow.actions.savefile",
    "WFWorkflowActionParameters": {
        "WFInput": {"Value": {"Type": "Variable", "Variable": "Contents of URL"}},
        "WFSaveFileAskWhere": True,
        "WFFileDestinationPath": "Documents/",
    }
}

WFWorkflow["WFWorkflowActions"] = [
    action1, action2, action3, action4, action5,
    action6, action7, action8, action9, action10, action11
]

# Write as binary plist
output_path = "YouTube_Downloader.shortcut"
with open(output_path, "wb") as f:
    plistlib.dump(WFWorkflow, f, fmt=plistlib.FMT_BINARY)

print(f"Created: {output_path}")
