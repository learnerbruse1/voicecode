loadAudioDevices().then(loadConfig).then(() => pollModelStatus(true));
setInterval(() => pollModelStatus(false), 3000);
setInterval(updateStats, 10000);
applyTranslations();
