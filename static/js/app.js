function app() {
    return {
        tab: 'url',
        urlInput: '',
        formatKind: 'video',
        videoQuality: '720',
        audioCodec: 'mp3',
        audioBitrate: '192',
        downloading: false,
        downloadingId: null,
        lastDownload: null,
        urlJob: null, // {id, progress, status, filename}
        status: '',
        statusType: 'info',
        
        searchQuery: '',
        searching: false,
        searched: false,
        searchResults: [],
        selectedResult: null,
        pickingId: null,
        pickingInfo: null,
        pickingLoading: false,
        pickKind: 'video',
        pickHeight: '720',
        pickCodec: 'mp3',
        pickBitrate: '192',
        progressById: {}, // id -> {progress, status, filename}
        
        files: [],
        storageStats: {},
        
        showCookies: false,
        cookiePlatforms: ['youtube', 'facebook', 'tiktok', 'twitter', 'instagram'],
        cookieStatus: {},
        
        init() {
            this.loadFiles();
            this.loadCookieStatus();
        },
        
        async api(path, options = {}) {
            const res = await fetch('/api/v1' + path, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                ...options
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw data;
            return data;
        },
        
        setStatus(msg, type = 'info') {
            this.status = msg;
            this.statusType = type;
        },
        
        clearStatus() {
            this.status = '';
        },

        async fetchInfo(url) {
            const data = await this.api('/info?url=' + encodeURIComponent(url));
            return data;
        },
        
        async startDownloadFromUrl() {
            if (!this.urlInput.trim() || this.downloading) return;
            const url = this.urlInput.trim();
            this.downloading = true;
            this.urlJob = { progress: 0, status: 'pending', filename: '' };
            this.clearStatus();
            // si on n'a pas encore analyse, on utilise les choix globaux directement
            try {
                const job = await this.api('/download', {
                    method: 'POST',
                    body: JSON.stringify({
                        url: url,
                        kind: this.formatKind,
                        height: this.videoQuality,
                        codec: this.audioCodec,
                        bitrate: this.audioBitrate
                    })
                });
                this.urlJob.id = job.job_id;
                this.setStatus('⏳ Téléchargement démarré...', 'info');
                await this.pollJob(job.job_id, (j) => {
                    this.urlJob.progress = j.progress;
                    this.urlJob.status = j.status;
                    if (j.result) this.urlJob.filename = j.result.filename;
                });
                // pollJob met lastDownload
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || e.message || 'Erreur'), 'error');
                this.urlJob = null;
            } finally {
                this.downloading = false;
            }
        },

        async pollJob(jobId, onProgress) {
            while (true) {
                await new Promise(r => setTimeout(r, 900));
                const job = await this.api('/download/' + jobId);
                if (onProgress) onProgress(job);
                if (job.status === 'downloading') {
                    if (!this.urlJob) this.setStatus(`⬇️ ${Math.round(job.progress)}%`, 'info');
                } else if (job.status === 'processing') {
                    if (!this.urlJob) this.setStatus('⚙️ Traitement...', 'info');
                } else if (job.status === 'completed') {
                    this.lastDownload = job.result;
                    if (!this.urlJob) this.setStatus('✅ Prêt : ' + job.result.filename, 'success');
                    this.loadFiles();
                    break;
                } else if (job.status === 'failed') {
                    throw job.error;
                }
            }
        },
        
        async doSearch() {
            if (!this.searchQuery.trim() || this.searching) return;
            this.searching = true;
            this.searched = true;
            this.searchResults = [];
            this.pickingId = null;
            this.setStatus('🔍 Recherche...', 'info');
            
            try {
                const res = await this.api(`/search?q=${encodeURIComponent(this.searchQuery.trim())}&per_page=12`);
                this.searchResults = res.results;
                this.progressById = {};
                this.setStatus(`${res.results.length} résultat(s)`, 'success');
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || 'Erreur recherche'), 'error');
            } finally {
                this.searching = false;
            }
        },
        
        selectResult(result) {
            this.selectedResult = result;
        },

        async openPicker(result) {
            if (this.pickingId === result.id) { this.pickingId = null; return; }
            this.pickingId = result.id;
            this.pickingInfo = null;
            this.pickingLoading = true;
            this.pickKind = this.formatKind;
            this.pickHeight = this.videoQuality;
            this.pickCodec = this.audioCodec;
            this.pickBitrate = this.audioBitrate;
            try {
                const info = await this.fetchInfo(result.url);
                this.pickingInfo = info;
                // adapter les choix aux formats dispo
                if (!info.supports_video) this.pickKind = 'audio';
                if (!info.supports_audio && info.supports_video) this.pickKind = 'video';
                // filtrer qualites proposees
                if (info.formats && info.formats.video && info.formats.video.length) {
                    const vs = info.formats.video;
                    if (!vs.includes(this.pickHeight) && this.pickHeight !== 'best') {
                        // prendre la plus proche disponible
                        this.pickHeight = vs[0] || '720';
                        if (this.pickHeight.endsWith('p')) this.pickHeight = this.pickHeight.replace('p','');
                    }
                }
            } catch (e) {
                // pas bloquant, on garde les choix globaux
                console.warn('info failed', e);
            } finally {
                this.pickingLoading = false;
            }
        },

        closePicker() { this.pickingId = null; this.pickingInfo = null; },
        
        async confirmPickerDownload(result) {
            if (this.downloadingId) return;
            this.downloadingId = result.id;
            this.progressById[result.id] = { progress: 0, status: 'pending', filename: result.title };
            this.clearStatus();
            try {
                const job = await this.api('/search/download', {
                    method: 'POST',
                    body: JSON.stringify({
                        video_id: result.id,
                        kind: this.pickKind,
                        height: this.pickHeight,
                        codec: this.pickCodec,
                        bitrate: this.pickBitrate
                    })
                });
                await this.pollJob(job.job_id, (j) => {
                    this.progressById[result.id] = { progress: j.progress, status: j.status, filename: j.result ? j.result.filename : result.title };
                });
                this.setStatus('✅ ' + result.title.substring(0,35) + ' → prêt', 'success');
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || e.message || 'Erreur'), 'error');
                this.progressById[result.id] = { progress: 0, status: 'failed', filename: result.title };
            } finally {
                this.downloadingId = null;
                setTimeout(() => { this.pickingId = null; }, 800);
            }
        },
        
        async downloadFromSearch(result) {
            // legacy: ouvre le picker au lieu de telecharger direct
            this.openPicker(result);
        },
        
        async loadFiles() {
            try {
                const res = await this.api('/files');
                this.files = res.files;
                this.storageStats = {
                    total_size: res.total_size,
                    max_size: res.max_size,
                    usage_percent: res.usage_percent
                };
            } catch (e) {
                console.error('Load files failed:', e);
            }
        },
        
        async saveToFiles(file) {
            const url = '/api/v1/files/' + encodeURIComponent(file.name);
            try {
                try {
                    const res = await fetch(url);
                    if (!res.ok) throw new Error('Fichier introuvable');
                    const blob = await res.blob();
                    const f = new File([blob], file.name, { type: blob.type || 'application/octet-stream' });
                    if (navigator.share && navigator.canShare && navigator.canShare({ files: [f] })) {
                        await navigator.share({ files: [f], title: file.name });
                        this.setStatus('✅ Choisis "Enregistrer dans Fichiers" → Documents → Inbox', 'success');
                        return;
                    }
                    const blobUrl = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    a.download = file.name;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => { URL.revokeObjectURL(blobUrl); a.remove(); }, 1000);
                    this.setStatus('✅ Fichier téléchargé — ouvre-le puis "Enregistrer dans Fichiers" → Inbox', 'success');
                    return;
                } catch (shareErr) {
                    if (shareErr.name === 'AbortError') return;
                }
                const a2 = document.createElement('a');
                a2.href = url;
                a2.download = file.name;
                a2.target = '_blank';
                document.body.appendChild(a2);
                a2.click();
                a2.remove();
                this.setStatus('✅ Si le fichier s\'ouvre, fais Partager → Enregistrer dans Fichiers → Inbox', 'success');
            } catch (e) {
                if (e.name !== 'AbortError') this.setStatus('❌ ' + e.message, 'error');
            }
        },
        async saveLastDownload() {
            if (!this.lastDownload) return;
            await this.saveToFiles({ name: this.lastDownload.filename });
        },
        
        openFile(file) {
            window.open('/api/v1/files/' + encodeURIComponent(file.name), '_blank');
        },
        
        async deleteFile(file) {
            if (!confirm('Supprimer ' + file.name + ' ?')) return;
            try {
                await this.api('/files/' + encodeURIComponent(file.name), { method: 'DELETE' });
                this.setStatus('🗑️ Supprimé', 'success');
                this.loadFiles();
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || 'Erreur suppression'), 'error');
            }
        },
        
        async cleanupFiles() {
            this.setStatus('🧹 Nettoyage...', 'info');
            try {
                const res = await this.api('/files/cleanup', { method: 'POST' });
                this.setStatus(`✅ ${res.message}`, 'success');
                this.loadFiles();
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || 'Erreur'), 'error');
            }
        },
        
        async loadCookieStatus() {
            try {
                const res = await this.api('/cookies');
                this.cookieStatus = res.cookies;
            } catch (e) {
                console.error('Cookie status failed:', e);
            }
        },
        
        async saveCookies(platform) {
            const textarea = document.getElementById('cookies-' + platform);
            const content = textarea.value.trim();
            if (!content) return;
            
            try {
                await this.api('/cookies/' + platform, {
                    method: 'POST',
                    body: JSON.stringify({ platform, content })
                });
                this.setStatus(`✅ Cookies ${platform} enregistrés`, 'success');
                this.loadCookieStatus();
                textarea.value = '';
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || 'Erreur'), 'error');
            }
        },
        
        async deleteCookies(platform) {
            try {
                await this.api('/cookies/' + platform, { method: 'DELETE' });
                this.setStatus(`🗑️ Cookies ${platform} supprimés`, 'success');
                this.loadCookieStatus();
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || 'Erreur'), 'error');
            }
        },
        
        formatSize(bytes) {
            if (bytes < 1024) return bytes + ' o';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' Ko';
            if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' Mo';
            return (bytes / 1024 / 1024 / 1024).toFixed(1) + ' Go';
        },
        
        formatNumber(n) {
            if (n >= 1e9) return (n / 1e9).toFixed(1) + 'M';
            if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
            if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
            return n.toString();
        }
    };
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
}
