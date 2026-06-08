/* Fortune SCM App - Frontend Application Logic */
/* API base URL */
const API_BASE = 'http://localhost:8765';

/* ────────────────────────────────────────
   Alpine.js Global Store & Data
   ──────────────────────────────────────── */
document.addEventListener('alpine:init', () => {

  // Global app store
  Alpine.store('app', {
    currentPage: 'dashboard',
    sidebarOpen: true,
    toasts: [],
    linkedinStatus: 'unknown',

    navigate(page) {
      this.currentPage = page;
      // Load page data
      if (typeof window.loadPageData === 'function') {
        window.loadPageData(page);
      }
    },

    addToast(type, message) {
      const id = Date.now();
      this.toasts.push({ id, type, message });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 4000);
    }
  });
});

/* ────────────────────────────────────────
   API Helper
   ──────────────────────────────────────── */
const api = {
  async get(endpoint) {
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      console.error(`GET ${endpoint} failed:`, err);
      throw err;
    }
  },

  async post(endpoint, data) {
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      console.error(`POST ${endpoint} failed:`, err);
      throw err;
    }
  },

  async put(endpoint, data) {
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      console.error(`PUT ${endpoint} failed:`, err);
      throw err;
    }
  },

  async del(endpoint) {
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      console.error(`DELETE ${endpoint} failed:`, err);
      throw err;
    }
  },

  async upload(endpoint, formData) {
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      console.error(`UPLOAD ${endpoint} failed:`, err);
      throw err;
    }
  }
};

/* ────────────────────────────────────────
   Page Data Loader
   ──────────────────────────────────────── */
window.loadPageData = function(page) {
  switch(page) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'linkedin':
      loadLinkedIn();
      break;
    case 'materials':
      loadMaterials();
      break;
    case 'ai-posts':
      loadAIPosts();
      break;
    case 'customers':
      loadCustomers();
      break;
    case 'settings':
      loadSettings();
      break;
  }
};

/* ────────────────────────────────────────
   Dashboard
   ──────────────────────────────────────── */
function loadDashboard() {
  const el = document.getElementById('dashboard-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  // Load stats
  api.get('/api/dashboard/stats')
    .then(res => {
      data.stats = res.data || res;
      data.statsLoading = false;
    })
    .catch(() => {
      data.statsLoading = false;
    });

  // Load activities
  api.get('/api/dashboard/activities')
    .then(res => {
      data.activities = res.data || res || [];
      data.activitiesLoading = false;
    })
    .catch(() => {
      data.activitiesLoading = false;
    });

  // Load linkedin status
  api.get('/api/linkedin/status')
    .then(res => {
      Alpine.store('app').linkedinStatus = (res.data || res).status || 'unknown';
    })
    .catch(() => {
      Alpine.store('app').linkedinStatus = 'offline';
    });
}

/* ────────────────────────────────────────
   LinkedIn Automation
   ──────────────────────────────────────── */
function loadLinkedIn() {
  const el = document.getElementById('linkedin-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  // Load quotas
  api.get('/api/linkedin/quotas')
    .then(res => {
      data.quotas = res.data || res;
      data.quotasLoading = false;
    })
    .catch(() => {
      data.quotasLoading = false;
    });
}

function searchLinkedIn(data) {
  data.searching = true;
  const params = new URLSearchParams();
  if (data.search.industry) params.set('industry', data.search.industry);
  if (data.search.title) params.set('title', data.search.title);
  if (data.search.location) params.set('location', data.search.location);
  if (data.search.keywords) params.set('keywords', data.search.keywords);

  api.get(`/api/linkedin/search?${params.toString()}`)
    .then(res => {
      data.results = res.data || res || [];
      data.searching = false;
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '搜索失败: ' + err.message);
      data.searching = false;
    });
}

function batchConnect(data) {
  const selected = data.results.filter((_, i) => data.selected[i]);
  if (selected.length === 0) {
    Alpine.store('app').addToast('info', '请先选择目标客户');
    return;
  }
  data.batchLoading = true;
  api.post('/api/linkedin/connect', { profiles: selected.map(r => r.url || r.id) })
    .then(res => {
      Alpine.store('app').addToast('success', `已发送 ${selected.length} 个好友请求`);
      data.batchLoading = false;
      loadLinkedIn();
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '操作失败: ' + err.message);
      data.batchLoading = false;
    });
}

function batchMessage(data) {
  const selected = data.results.filter((_, i) => data.selected[i]);
  if (selected.length === 0) {
    Alpine.store('app').addToast('info', '请先选择目标客户');
    return;
  }
  if (!data.messageText) {
    Alpine.store('app').addToast('info', '请输入消息内容');
    return;
  }
  data.batchLoading = true;
  api.post('/api/linkedin/message', {
    profiles: selected.map(r => r.url || r.id),
    message: data.messageText
  })
    .then(res => {
      Alpine.store('app').addToast('success', `已发送 ${selected.length} 条消息`);
      data.batchLoading = false;
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '操作失败: ' + err.message);
      data.batchLoading = false;
    });
}

/* ────────────────────────────────────────
   Content Library (Materials)
   ──────────────────────────────────────── */
function loadMaterials() {
  const el = document.getElementById('materials-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  api.get('/api/materials')
    .then(res => {
      data.materials = res.data || res || [];
      data.loading = false;
    })
    .catch(() => {
      data.loading = false;
    });

  // Load tags
  api.get('/api/materials/tags')
    .then(res => {
      data.tags = res.data || res || [];
    })
    .catch(() => {});
}

function saveMaterial(data) {
  if (!data.form.title || !data.form.content) {
    Alpine.store('app').addToast('info', '请填写标题和内容');
    return;
  }
  data.saving = true;
  const payload = {
    title: data.form.title,
    content: data.form.content,
    tags: data.form.tags.split(',').map(t => t.trim()).filter(Boolean)
  };

  const call = data.form.id
    ? api.put(`/api/materials/${data.form.id}`, payload)
    : api.post('/api/materials', payload);

  call.then(() => {
      Alpine.store('app').addToast('success', data.form.id ? '素材已更新' : '素材已创建');
      data.showModal = false;
      data.form = { id: null, title: '', content: '', tags: '' };
      loadMaterials();
      data.saving = false;
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '保存失败: ' + err.message);
      data.saving = false;
    });
}

function deleteMaterial(id) {
  if (!confirm('确定删除此素材？')) return;
  api.del(`/api/materials/${id}`)
    .then(() => {
      Alpine.store('app').addToast('success', '素材已删除');
      loadMaterials();
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '删除失败: ' + err.message);
    });
}

/* ────────────────────────────────────────
   AI Posts
   ──────────────────────────────────────── */
function loadAIPosts() {
  const el = document.getElementById('aiposts-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  api.get('/api/content/history')
    .then(res => {
      data.posts = res.data || res || [];
      data.loading = false;
    })
    .catch(() => {
      data.loading = false;
    });
}

function generatePost(data) {
  data.generating = true;
  data.preview = '';
  api.post('/api/content/generate', { topic: data.topic || '' })
    .then(res => {
      data.preview = (res.data || res).content || (res.data || res).text || '';
      data.generating = false;
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '生成失败: ' + err.message);
      data.generating = false;
    });
}

function publishPost(data) {
  if (!data.preview) {
    Alpine.store('app').addToast('info', '请先生成内容');
    return;
  }
  data.publishing = true;
  api.post('/api/content/publish', { content: data.preview })
    .then(res => {
      Alpine.store('app').addToast('success', '动态已发布');
      data.preview = '';
      data.publishing = false;
      loadAIPosts();
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '发布失败: ' + err.message);
      data.publishing = false;
    });
}

/* ────────────────────────────────────────
   Customer Management
   ──────────────────────────────────────── */
function loadCustomers() {
  const el = document.getElementById('customers-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  const params = new URLSearchParams();
  if (data.searchQuery) params.set('q', data.searchQuery);
  if (data.filterStatus) params.set('status', data.filterStatus);

  api.get(`/api/customers?${params.toString()}`)
    .then(res => {
      data.customers = res.data || res || [];
      data.loading = false;
    })
    .catch(() => {
      data.loading = false;
    });
}

function viewCustomer(data, customer) {
  data.detail = customer;
  data.showDetail = true;

  // Load follow-up records
  api.get(`/api/customers/${customer.id}/records`)
    .then(res => {
      data.records = res.data || res || [];
    })
    .catch(() => {
      data.records = [];
    });
}

function addFollowUp(data) {
  if (!data.followUpNote) return;
  api.post(`/api/customers/${data.detail.id}/records`, {
    note: data.followUpNote,
    type: data.followUpType || 'note'
  })
    .then(() => {
      Alpine.store('app').addToast('success', '跟进记录已添加');
      data.followUpNote = '';
      viewCustomer(data, data.detail);
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '操作失败: ' + err.message);
    });
}

/* ────────────────────────────────────────
   Settings
   ──────────────────────────────────────── */
function loadSettings() {
  const el = document.getElementById('settings-data');
  if (!el || !el.__x) return;
  const data = el.__x.$data;

  api.get('/api/settings')
    .then(res => {
      const s = res.data || res;
      Object.assign(data.config, s);
      data.loading = false;
    })
    .catch(() => {
      data.loading = false;
    });
}

function saveSettings(data, section) {
  data.saving = true;
  api.post('/api/settings', data.config)
    .then(() => {
      Alpine.store('app').addToast('success', '设置已保存');
      data.saving = false;
    })
    .catch(err => {
      Alpine.store('app').addToast('error', '保存失败: ' + err.message);
      data.saving = false;
    });
}

/* ────────────────────────────────────────
   Utility Functions
   ──────────────────────────────────────── */
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const d = new Date(dateStr);
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
  return d.toLocaleDateString('zh-CN');
}

function truncate(str, len = 100) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

/* ────────────────────────────────────────
   Initial Load
   ──────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Check LinkedIn status on startup
  api.get('/api/linkedin/status')
    .then(res => {
      Alpine.store('app').linkedinStatus = (res.data || res).status || 'unknown';
    })
    .catch(() => {
      Alpine.store('app').linkedinStatus = 'offline';
    });
});
