# Installation Guide for Extended Gemini Conversation

## Overview
This integration has been converted from Extended OpenAI Conversation to work with Google's Gemini API. It provides conversation capabilities with Home Assistant using Gemini models.

## Requirements
- Home Assistant 2026.2.0b0 or newer
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

## Installation Methods

### Method 1: HACS (Recommended)
1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/willianrod/extended_gemini_conversation`
6. Select category: "Integration"
7. Click "Add"
8. Find "Extended Gemini Conversation" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Method 2: Manual Installation
1. Download the `custom_components/extended_openai_conversation` folder from this repository
2. Copy the entire folder to your Home Assistant's `custom_components` directory
   - The path should be: `<config directory>/custom_components/extended_openai_conversation`
3. Restart Home Assistant

## Configuration

### Initial Setup
1. Go to **Settings** > **Devices & Services**
2. Click the **Add Integration** button in the bottom right corner
3. Search for "Extended Gemini Conversation"
4. Enter your Google Gemini API Key when prompted
5. (Optional) Configure base URL if needed - defaults to Google's Gemini API
6. Complete the setup

### Voice Assistant Configuration
1. Go to **Settings** > **Voice Assistants**
2. Click on your assistant (usually "Home Assistant")
3. In the **Conversation agent** tab, select "Extended Gemini Conversation"
4. Save your changes

### Exposing Entities
For the assistant to control your devices, you need to expose entities:
1. Go to **Settings** > **Voice Assistants** > **Expose** tab
2. Select which entities you want the assistant to be able to control
3. Only exposed entities will be available to the Gemini conversation agent

## Default Model
The integration uses `gemini-2.5-flash` by default, which provides:
- Fast response times
- Good reasoning capabilities
- Function calling support
- Cost-effective usage

You can change the model in the integration options if needed.

## Features
- ✅ Service calls to control Home Assistant devices
- ✅ Function calling for custom automations
- ✅ History retrieval
- ✅ External API calls
- ✅ Web scraping
- ✅ Image queries (vision capabilities)
- ✅ Automation creation
- ✅ Custom templates

## Troubleshooting

### Integration not loading
- Ensure you've restarted Home Assistant after installation
- Check the Home Assistant logs for errors
- Verify your API key is correct

### API Key Issues
- Make sure you have a valid Google Gemini API key
- Check that the API key has the correct permissions
- Verify you haven't exceeded rate limits

### Device Control Issues
- Ensure entities are exposed in Voice Assistant settings
- Check that the entity IDs are correct
- Review function definitions in the integration options

## Support
For issues, questions, or feature requests, please visit:
https://github.com/willianrod/extended_gemini_conversation/issues

## Credits
This integration is derived from [Extended OpenAI Conversation](https://github.com/jekalmin/extended_openai_conversation) by jekalmin.
