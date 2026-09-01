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
        status: '',
        statusType: 'info',
        
        searchQuery: '',
        searching: false,
        searched: false,
        searchResults: [],
        selectedResult: null,
        
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
        
        async startDownloadFromUrl() {
            if (!this.urlInput.trim() || this.downloading) return;
            this.downloading = true;
            this.clearStatus();
            
            try {
                const job = await this.api('/download', {
                    method: 'POST',
                    body: JSON.stringify({
                        url: this.urlInput.trim(),
                        kind: this.formatKind,
                        height: this.videoQuality,
                        codec: this.audioCodec,
                        bitrate: this.audioBitrate
                    })
                });
                
                this.setStatus('⏳ Téléchargement démarré...', 'info');
                await this.pollJob(job.job_id);
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || e.message || 'Erreur'), 'error');
            } finally {
                this.downloading = false;
            }
        },
        
        async pollJob(jobId) {
            while (true) {
                await new Promise(r => setTimeout(r, 1000));
                const job = await this.api('/download/' + jobId);
                
                if (job.status === 'downloading') {
                    this.setStatus(`⬇️ ${Math.round(job.progress)}% — ${job.result ? job.result.filename : ''}`, 'info');
                } else if (job.status === 'processing') {
                    this.setStatus('⚙️ Traitement...', 'info');
                } else if (job.status === 'completed') {
                    this.lastDownload = job.result;
                    this.setStatus('✅ Prêt : ' + job.result.filename, 'success');
                    this.urlInput = '';
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
            this.setStatus('🔍 Recherche...', 'info');
            
            try {
                const res = await this.api(`/search?q=${encodeURIComponent(this.searchQuery.trim())}&per_page=20`);
                this.searchResults = res.results;
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
        
        async downloadFromSearch(result) {
            if (this.downloadingId) return;
            this.downloadingId = result.id;
            this.clearStatus();
            try {
                const job = await this.api('/search/download', {
                    method: 'POST',
                    body: JSON.stringify({
                        video_id: result.id,
                        kind: this.formatKind,
                        height: this.videoQuality,
                        codec: this.audioCodec,
                        bitrate: this.audioBitrate
                    })
                });
                this.setStatus('⏳ ' + result.title.substring(0,40) + '…', 'info');
                await this.pollJob(job.job_id);
            } catch (e) {
                this.setStatus('❌ ' + (e.user_message || e.message || 'Erreur'), 'error');
            } finally {
                this.downloadingId = null;
            }
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
                // 1) Essai via Web Share API (iOS : permet Choisir -> Enregistrer dans Fichiers -> Documents > Inbox)
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
                    // fallback blob URL meme si share non disponible
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
                    // dernier fallback : lien direct avec Content-Disposition attachment
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