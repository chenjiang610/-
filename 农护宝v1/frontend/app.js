// 通用工具函数
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text || '';
}

function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html || '';
}

function showStatus(id, message, type = 'info') {
  const statusEl = document.getElementById(id);
  if (!statusEl) return;
  
  statusEl.innerHTML = `
    <div class="status-icon ${type}"></div>
    <span class="status-text">${message}</span>
  `;
  statusEl.className = `status-indicator ${type}`;
}

// 文件上传处理
function setupFileUpload() {
  const uploadAreas = document.querySelectorAll('.file-upload-area');
  
  uploadAreas.forEach(area => {
    const fileInput = area.querySelector('input[type="file"]');
    const uploadButton = area.querySelector('.upload-button');
    const placeholder = area.querySelector('.upload-placeholder');
    
    if (!fileInput || !uploadButton) return;
    
    // 点击按钮触发文件选择
    uploadButton.addEventListener('click', () => {
      fileInput.click();
    });
    
    // 拖拽上传
    area.addEventListener('dragover', (e) => {
      e.preventDefault();
      area.classList.add('dragover');
    });
    
    area.addEventListener('dragleave', () => {
      area.classList.remove('dragover');
    });
    
    area.addEventListener('drop', (e) => {
      e.preventDefault();
      area.classList.remove('dragover');
      
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        handleFileSelect(fileInput, placeholder);
      }
    });
    
    // 文件选择处理
    fileInput.addEventListener('change', () => {
      handleFileSelect(fileInput, placeholder);
    });
  });
}

function handleFileSelect(input, placeholder) {
  const file = input.files[0];
  if (!file) return;
  
  if (placeholder) {
    placeholder.innerHTML = `
      <div class="file-info">
        <div class="file-icon">📄</div>
        <div class="file-details">
          <p class="file-name">${file.name}</p>
          <p class="file-size">${formatFileSize(file.size)}</p>
        </div>
      </div>
    `;
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 诊断功能
function setupDiagnose() {
  const diagnoseForm = document.getElementById('diagnose-form');
  if (!diagnoseForm) return;
  
  diagnoseForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('image-file');
    const topk = document.getElementById('topk').value;
    
    if (!fileInput.files.length) {
      showStatus('diagnose-status', '请先选择图片', 'error');
      return;
    }
    
    showStatus('diagnose-status', '正在诊断...', 'loading');
    setHTML('predictions', '');
    setHTML('report', '');
    
    const formData = new FormData();
    formData.append('image', fileInput.files[0]);
    
    try {
      const tk = localStorage.getItem('token');
      const headers = tk ? { 'Authorization': `Bearer ${tk}` } : {};
      const res = await fetch(`/diagnose?top_k=${encodeURIComponent(topk)}`, {
        method: 'POST',
        headers,
        body: formData
      });
      
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || '诊断接口调用失败');
      }
      
      const data = await res.json();
      showStatus('diagnose-status', '诊断完成', 'success');
      displayDiagnoseResults(data);
      loadHistory();
      
    } catch (error) {
      showStatus('diagnose-status', error.message, 'error');
      console.error('诊断错误:', error);
    }
  });
}

function displayDiagnoseResults(data) {
  const predictions = data.predictions || [];
  const report = data.report || null;
  
  if (predictions.length > 0) {
    const predictionHTML = `
      <div class="prediction-results">
        <h4 class="results-title">识别结果 (Top ${predictions.length})</h4>
        <div class="prediction-list">
          ${predictions.map((p, index) => {
            const score = Math.min(100, Math.round((p.score || 0) * 100));
            const knowledgeTag = p.has_knowledge ? '<span class="kb-chip">知识库支持</span>' : '<span class="kb-chip">待补充</span>';
            return `
              <div class="prediction-item">
                <div class="prediction-rank">${index + 1}</div>
                <div class="prediction-content">
                  <div class="prediction-header">
                    <span class="crop-name">${p.crop || '未知作物'}</span>
                    <span class="disease-name">· ${p.disease || '未知病害'}</span>
                    ${knowledgeTag}
                  </div>
                  <div class="prediction-details">
                    <span class="confidence">置信度 ${score.toFixed(0)}%</span>
                    <div class="confidence-bar"><span style="width:${score}%"></span></div>
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
    setHTML('predictions', predictionHTML);
  } else {
    setHTML('predictions', '<p class="empty-subtext">暂无预测结果</p>');
  }
  
  if (report) {
    const confidence = Math.min(100, ((report.confidence || 0) * 100).toFixed(2));
    const badge = report.kb_used ? '知识库支撑' : 'AI生成';
    const reportHTML = `
      <div class="diagnose-report">
        <div class="report-hero">
          <div class="hero-main">
            <span class="hero-label">识别报告</span>
            <h4 class="hero-title">${report.crop || '未知作物'} · ${report.disease || '待确认'}</h4>
            <p class="hero-subtitle">标签：${report.label || '-'} · 置信度 ${confidence}%</p>
          </div>
          <span class="hero-badge">${badge}</span>
        </div>
        <div class="report-grid">
          <div class="report-item">
            <span class="report-label">作物</span>
            <span class="report-value">${report.crop || '未知'}</span>
          </div>
          <div class="report-item">
            <span class="report-label">病害</span>
            <span class="report-value">${report.disease || '未知'}</span>
          </div>
          <div class="report-item">
            <span class="report-label">置信度</span>
            <span class="report-value">${confidence}%</span>
          </div>
          <div class="report-item">
            <span class="report-label">数据来源</span>
            <span class="report-value">${report.kb_used ? '知识库' : 'AI生成'}</span>
          </div>
        </div>
        <div class="report-section">
          <h5>症状</h5>
          <p>${report.symptoms || '暂未收录'}</p>
        </div>
        <div class="report-section">
          <h5>描述</h5>
          <p>${report.description || '暂未收录'}</p>
        </div>
        <div class="report-section">
          <h5>防治方法</h5>
          <p>${report.prevention || '暂未收录'}</p>
        </div>
        <div class="report-meta">
          <span>${report.generated ? '由AI生成补全' : '来源于知识库条目'}</span>
          <span>更新时间：${new Date().toLocaleString()}</span>
        </div>
      </div>
    `;
    setHTML('report', reportHTML);
  } else {
    setHTML('report', '');
  }
  
  const resultsContent = document.getElementById('results-content');
  if (resultsContent) {
    resultsContent.style.display = 'none';
  }
}

// 问答功能
function setupQA() {
  const qaForm = document.getElementById('qa-form');
  if (!qaForm) return;
  
  const questionInput = document.getElementById('question');
  const charCount = document.querySelector('.char-count');
  
  // 字符计数
  if (questionInput && charCount) {
    questionInput.addEventListener('input', () => {
      const length = questionInput.value.length;
      charCount.textContent = `${length} / 500`;
      
      if (length > 500) {
        charCount.style.color = 'var(--color-error)';
      } else {
        charCount.style.color = 'var(--text-muted)';
      }
    });
  }
  
  // 快速提问按钮
  const quickQuestions = document.querySelectorAll('.quick-question, .suggestion-tag');
  quickQuestions.forEach(button => {
    button.addEventListener('click', () => {
      const question = button.getAttribute('data-question');
      if (questionInput) {
        questionInput.value = question;
        questionInput.dispatchEvent(new Event('input'));
        questionInput.focus();
      }
    });
  });
  
  // 清除回答
  const clearButton = document.getElementById('clear-answer');
  if (clearButton) {
    clearButton.addEventListener('click', () => {
      setHTML('qa-answer', '');
      document.getElementById('answer-actions').style.display = 'none';
      const answerContent = document.getElementById('answer-content');
      if (answerContent) {
        answerContent.style.display = 'flex';
      }
      showStatus('qa-status', '等待提问', 'info');
    });
  }
  
  // 复制回答
  const copyButton = document.getElementById('copy-answer');
  if (copyButton) {
    copyButton.addEventListener('click', async () => {
      const answerText = document.getElementById('qa-answer')?.textContent;
      if (answerText) {
        try {
          await navigator.clipboard.writeText(answerText);
          copyButton.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M13 4L6 11L3 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>已复制</span>
          `;
          setTimeout(() => {
            copyButton.innerHTML = `
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M12 4H8C6.89543 4 6 4.89543 6 6V10C6 11.1046 6.89543 12 8 12H12C13.1046 12 14 11.1046 14 10V6C14 4.89543 13.1046 4 12 4Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M4 8V12C4 13.1046 4.89543 14 6 14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span>复制</span>
            `;
          }, 2000);
        } catch (err) {
          console.error('复制失败:', err);
        }
      }
    });
  }
  
  qaForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const question = questionInput.value.trim();
    if (!question) {
      showStatus('qa-status', '请输入问题', 'error');
      return;
    }
    
    if (question.length > 500) {
      showStatus('qa-status', '问题长度不能超过500字', 'error');
      return;
    }
    
    showStatus('qa-status', '正在思考...', 'loading');
    setHTML('qa-answer', '');
    document.getElementById('answer-actions').style.display = 'none';
    try {
      const createRes = await fetch('/qa/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, fast: true })
      });
      if (!createRes.ok) {
        const t = await createRes.text();
        throw new Error(t || '创建任务失败');
      }
      const { task_id } = await createRes.json();
      const startTime = Date.now();
      const poll = setInterval(async () => {
        try {
          const stRes = await fetch(`/qa/task/${task_id}`);
          if (!stRes.ok) return;
          const st = await stRes.json();
          if (st.status === 'done') {
            clearInterval(poll);
            showStatus('qa-status', '回答完成', 'success');
            const data = st.result || {};
            const answerHTML = `
              <div class="qa-answer">
                <div class="answer-header">
                  <span class="answer-label">AI回答</span>
                  <span class="answer-time">${new Date().toLocaleTimeString()}</span>
                </div>
                <div class="answer-content">${data.answer || ''}</div>
              </div>
            `;
            setHTML('qa-answer', answerHTML);
            if (data.graph) {
              renderGraph(data.graph, 'qa-graph');
            }
            const answerContent = document.getElementById('answer-content');
            if (answerContent) {
              answerContent.style.display = 'none';
            }
            document.getElementById('answer-actions').style.display = 'block';
          } else if (st.status === 'error') {
            clearInterval(poll);
            showStatus('qa-status', st.error || '生成失败', 'error');
          } else {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            showStatus('qa-status', `正在思考... ${elapsed}s`, 'loading');
          }
        } catch (err) {}
      }, 1500);
    } catch (error) {
      showStatus('qa-status', error.message, 'error');
      console.error('问答错误:', error);
    }
  });
}

function renderGraph(graph, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const nodeHtml = nodes.map(n => `
    <div class="graph-node ${n.type}">${n.label}</div>
  `).join('');
  const edgeHtml = edges.map(e => `
    <div class="graph-edge">
      <span>${e.source.split(':')[1]}</span>
      <span>⇄</span>
      <span>${e.target.split(':')[1]}</span>
    </div>
  `).join('');
  el.innerHTML = `
    <div class="graph-section">
      <h4 class="report-title">知识图谱</h4>
      <div class="graph-nodes">${nodeHtml}</div>
      <div class="graph-edges">${edgeHtml}</div>
    </div>
  `;
}

// 知识库功能
function setupKnowledgeBase() {
  const searchForm = document.getElementById('kb-search-form');
  const keywordInput = document.getElementById('kb-keyword');
  const placeholder = document.getElementById('kb-result-placeholder');

  const trendButtons = document.querySelectorAll('.kb-trend-button');
  trendButtons.forEach(button => {
    button.addEventListener('click', () => {
      if (!keywordInput) return;
      keywordInput.value = button.getAttribute('data-keyword') || '';
      keywordInput.focus();
      if (searchForm) {
        searchForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  if (!searchForm || !keywordInput) return;

  const runQuery = async (keyword) => {
    showStatus('kb-search-status', '正在查询...', 'loading');
    try {
      const res = await fetch(`/kb/query?keyword=${encodeURIComponent(keyword)}`);
      if (!res.ok) {
        throw new Error('查询失败，请稍后重试');
      }
      const data = await res.json();
      showStatus('kb-search-status', '查询完成', 'success');
      renderKBResults(data);
      if (placeholder) {
        placeholder.style.display = 'none';
      }
    } catch (error) {
      showStatus('kb-search-status', error.message || '查询失败', 'error');
    }
  };

  searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const keyword = keywordInput.value.trim();
    if (!keyword) {
      showStatus('kb-search-status', '请输入关键词', 'error');
      return;
    }
    const title = document.getElementById('kb-result-title');
    if (title) {
      title.textContent = `正在检索：${keyword}`;
    }
    runQuery(keyword);
  });
}

function renderKBResults(data) {
  const titleEl = document.getElementById('kb-result-title');
  if (titleEl) {
    titleEl.textContent = `关键字「${data.keyword}」 · 匹配 ${data.total_matches || 0} 条`;
  }

  const stats = data.stats || {};
  const topCrop = stats.top_crops && stats.top_crops.length ? stats.top_crops[0][0] : '—';
  setHTML('kb-result-summary', `
    <div class="kb-stat-chip">
      <div class="kb-stat-label">匹配条目</div>
      <div class="kb-stat-value">${data.total_matches || 0}</div>
    </div>
    <div class="kb-stat-chip">
      <div class="kb-stat-label">关联作物</div>
      <div class="kb-stat-value">${stats.unique_crops || 0}</div>
    </div>
    <div class="kb-stat-chip">
      <div class="kb-stat-label">关联病害</div>
      <div class="kb-stat-value">${stats.unique_diseases || 0}</div>
    </div>
    <div class="kb-stat-chip">
      <div class="kb-stat-label">热门作物</div>
      <div class="kb-stat-value">${topCrop}</div>
    </div>
  `);

  const entries = data.entries || [];
  if (!entries.length) {
    setHTML('kb-result-list', '<p class="empty-subtext">暂无匹配条目，请尝试其他关键词</p>');
    setHTML('kb-featured-report', `
      <div class="kb-report-card">
        <div class="kb-report-header">
          <div>
            <p class="kb-report-label">查询报告</p>
            <h4>暂未找到相关条目</h4>
            <p class="kb-report-keyword">关键词：${data.keyword}</p>
          </div>
        </div>
        <div class="kb-report-body">
          <p>尝试更具体的病害名称、作物名称，或者检查拼写后再次搜索。</p>
        </div>
      </div>
    `);
    renderKBGraph(null);
    return;
  }

  setHTML('kb-result-list', entries.map(entry => `
    <div class="kb-entry-card">
      <div class="kb-entry-header">
        <div>
          <h4 class="kb-entry-title">${entry.crop || '未标注作物'} · ${entry.disease || '未标注病害'}</h4>
          <p class="kb-hint">标签：${entry.label}</p>
        </div>
        <div class="kb-chips">
          <span class="kb-chip">${entry.source === 'llm' ? 'AI生成' : '知识库'}</span>
          ${entry.generated ? '<span class="kb-chip">动态补全</span>' : ''}
        </div>
      </div>
      <div class="kb-entry-body">
        <div class="kb-entry-section">
          <h5>症状</h5>
          <p>${entry.symptoms || '暂未收录'}</p>
        </div>
        <div class="kb-entry-section">
          <h5>描述</h5>
          <p>${entry.description || '暂未收录'}</p>
        </div>
        <div class="kb-entry-section">
          <h5>防治方法</h5>
          <p>${entry.prevention || '暂未收录'}</p>
        </div>
      </div>
    </div>
  `).join(''));

  renderKBReport(entries[0], data.keyword, data.total_matches, stats);
}

function renderKBGraph(graph) {
  const container = document.getElementById('kb-graph');
  if (!container) return;
  const nodes = graph && graph.nodes ? graph.nodes : [];
  const edges = graph && graph.edges ? graph.edges : [];
  const relationCount = graph && typeof graph.count !== 'undefined' ? graph.count : edges.length;
  if (!nodes.length) {
    container.innerHTML = `
      <div class="empty-state">
        <p class="empty-text">暂无可视化图谱</p>
        <p class="empty-subtext">尝试使用更精准的关键词</p>
      </div>
    `;
    return;
  }
  const cropNodes = nodes.filter(n => n.type === 'crop');
  const diseaseNodes = nodes.filter(n => n.type === 'disease');
  container.innerHTML = `
    <div class="kb-graph-card">
      <h4 class="report-title">知识图谱 · 关联 ${relationCount || 0} 条</h4>
      <div class="kb-entry-section">
        <h5>作物节点</h5>
        <div class="graph-nodes">
          ${cropNodes.length ? cropNodes.map(n => `<span class="graph-pill crop">${n.label}</span>`).join('') : '<span class="graph-pill">暂无</span>'}
        </div>
      </div>
      <div class="kb-entry-section">
        <h5>病害节点</h5>
        <div class="graph-nodes">
          ${diseaseNodes.length ? diseaseNodes.map(n => `<span class="graph-pill disease">${n.label}</span>`).join('') : '<span class="graph-pill">暂无</span>'}
        </div>
      </div>
      <div class="kb-entry-section">
        <h5>关联关系</h5>
        <div class="graph-edge-list">
          ${edges.length ? edges.slice(0, 10).map(e => `
            <div class="graph-edge-card">
              <span>${e.source.split(':')[1]}</span>
              <span>⇄</span>
              <span>${e.target.split(':')[1]}</span>
            </div>
          `).join('') : '<span class="empty-subtext">暂无关联</span>'}
        </div>
      </div>
    </div>
  `;
}

function renderKBReport(entry, keyword, totalMatches, stats) {
  const container = document.getElementById('kb-featured-report');
  if (!container) return;
  if (!entry) {
    container.innerHTML = '';
    return;
  }
  const badge = entry.source === 'llm' ? 'AI补全' : '知识库';
  container.innerHTML = `
    <div class="kb-report-card">
      <div class="kb-report-header">
        <div>
          <p class="kb-report-label">查询报告</p>
          <h4>${entry.crop || '未标注作物'} · ${entry.disease || '未标注病害'}</h4>
          <p class="kb-report-keyword">关键词：${keyword} · 标签：${entry.label || '-'}</p>
        </div>
        <span class="kb-chip highlight">${badge}</span>
      </div>
      <div class="kb-report-metrics">
        <div class="kb-metric">
          <span class="kb-metric-label">匹配条目</span>
          <span class="kb-metric-value">${totalMatches || 0}</span>
        </div>
        <div class="kb-metric">
          <span class="kb-metric-label">关联作物</span>
          <span class="kb-metric-value">${stats?.unique_crops || 0}</span>
        </div>
        <div class="kb-metric">
          <span class="kb-metric-label">关联病害</span>
          <span class="kb-metric-value">${stats?.unique_diseases || 0}</span>
        </div>
      </div>
      <div class="kb-report-body">
        <div>
          <h5>症状要点</h5>
          <p>${entry.symptoms || '暂未收录'}</p>
        </div>
        <div>
          <h5>防治建议</h5>
          <p>${entry.prevention || '暂未收录'}</p>
        </div>
      </div>
    </div>
  `;
}

function setupKBHistory() {
  const listEl = document.getElementById('kb-history-list');
  if (!listEl) return;
  const tk = localStorage.getItem('token');
  if (!tk) {
    showStatus('kb-history-status', '未登录', 'error');
    setHTML('kb-history-list', '<p class="empty-subtext">请登录后查看历史识别记录</p>');
    setHTML('kb-insights', '<p class="empty-subtext">登录后可生成智能分析</p>');
    return;
  }
  showStatus('kb-history-status', '正在加载...', 'loading');
  (async () => {
    try {
      const resHist = await fetch('/diagnostics/history', { headers: { 'Authorization': `Bearer ${tk}` } });
      if (resHist.ok) {
        const data = await resHist.json();
        const list = (data.history || []).slice().reverse().slice(0, 10);
        const html = list.map(item => `
          <div class="kb-entry-card" data-time="${item.time || 0}">
            <div class="kb-entry-header">
              <div>
                <h4 class="kb-entry-title">${item.crop || '-'} · ${item.disease || '-'}</h4>
                <p class="kb-hint">时间：${new Date((item.time||0)*1000).toLocaleString()} · 置信度：${(((item.confidence||0)*100)||0).toFixed(1)}%</p>
              </div>
              <div class="kb-chips">
                ${item.generated ? '<span class="kb-chip">AI补全</span>' : '<span class="kb-chip">知识库</span>'}
              </div>
            </div>
            <div class="kb-entry-body">
              <div class="kb-entry-section">
                <button class="ask-button" data-action="view-report">查看报告</button>
              </div>
            </div>
          </div>
        `).join('');
        setHTML('kb-history-list', html || '<p class="empty-subtext">暂无历史记录</p>');
      }
      const resStat = await fetch('/status/analysis', { headers: { 'Authorization': `Bearer ${tk}` } });
      if (resStat.ok) {
        const stat = await resStat.json();
        const crops = stat.summary?.crops || {};
        const diseases = stat.summary?.diseases || {};
        const topCrop = Object.entries(crops).sort((a,b)=>b[1]-a[1])[0]?.[0] || '—';
        const topDisease = Object.entries(diseases).sort((a,b)=>b[1]-a[1])[0]?.[0] || '—';
        setHTML('kb-history-summary', `
          <div class="kb-stat-chip">
            <div class="kb-stat-label">历史条目</div>
            <div class="kb-stat-value">${(stat.trend||[]).length || 0}</div>
          </div>
          <div class="kb-stat-chip">
            <div class="kb-stat-label">高频作物</div>
            <div class="kb-stat-value">${topCrop}</div>
          </div>
          <div class="kb-stat-chip">
            <div class="kb-stat-label">高频病害</div>
            <div class="kb-stat-value">${topDisease}</div>
          </div>
        `);
      }
      showStatus('kb-history-status', '加载完成', 'success');
    } catch (e) {
      showStatus('kb-history-status', '加载失败', 'error');
    }
  })();
  // 点击查看历史报告
  listEl.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    const card = e.target.closest('.kb-entry-card');
    if (!card) return;
    const time = card.getAttribute('data-time');
    if (btn && btn.getAttribute('data-action') === 'view-report' && time) {
      try {
        const tk = localStorage.getItem('token');
        const res = await fetch(`/diagnostics/history/item?time=${encodeURIComponent(time)}`, { headers: { 'Authorization': `Bearer ${tk}` } });
        if (!res.ok) return;
        const data = await res.json();
        const rec = data.record || {};
        const report = rec.report || {};
        const container = document.getElementById('report') ? 'report' : 'kb-featured-report';
        const confidence = Math.min(100, ((rec.confidence || 0) * 100)).toFixed(2);
        const badge = rec.generated ? 'AI生成' : '知识库';
        const html = `
          <div class="diagnose-report">
            <div class="report-hero">
              <div class="hero-main">
                <span class="hero-label">历史诊断报告</span>
                <h4 class="hero-title">${rec.crop || '-'} · ${rec.disease || '-'}</h4>
                <p class="hero-subtitle">时间：${new Date((rec.time||0)*1000).toLocaleString()} · 置信度 ${confidence}%</p>
              </div>
              <span class="hero-badge">${badge}</span>
            </div>
            <div class="report-grid">
              <div class="report-item"><span class="report-label">作物</span><span class="report-value">${rec.crop || '-'}</span></div>
              <div class="report-item"><span class="report-label">病害</span><span class="report-value">${rec.disease || '-'}</span></div>
              <div class="report-item"><span class="report-label">置信度</span><span class="report-value">${confidence}%</span></div>
              <div class="report-item"><span class="report-label">数据来源</span><span class="report-value">${badge}</span></div>
            </div>
            <div class="report-section"><h5>症状</h5><p>${report.symptoms || report['症状'] || '暂未收录'}</p></div>
            <div class="report-section"><h5>描述</h5><p>${report.description || report['描述'] || '暂未收录'}</p></div>
            <div class="report-section"><h5>防治方法</h5><p>${report.prevention || report['防治方法'] || '暂未收录'}</p></div>
          </div>`;
        setHTML(container, html);
      } catch (err) {}
    }
  });
  showStatus('kb-insights-status', '正在分析...', 'loading');
  (async () => {
    try {
      const res = await fetch('/diagnostics/insights', { headers: { 'Authorization': `Bearer ${tk}` } });
      if (!res.ok) { const t = await res.text(); throw new Error(t || '分析失败'); }
      const data = await res.json();
      const txt = (data.insights || '').replace(/\n/g, '<br/>');
      setHTML('kb-insights', `
        <div class="kb-report-card">
          <div class="kb-report-body">
            <div>${txt || '暂无分析'}</div>
          </div>
        </div>
      `);
      showStatus('kb-insights-status', '分析完成', 'success');
    } catch (e) {
      showStatus('kb-insights-status', '分析失败', 'error');
    }
  })();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  enforceAuthGate();
  setupFileUpload();
  setupDiagnose();
  setupQA();
  setupKnowledgeBase();
  setupKBHistory();
  setupAuth();
  setupCommunity();
  
  // 添加页面切换动画
  document.body.style.opacity = '0';
  setTimeout(() => {
    document.body.style.transition = 'opacity 0.3s ease-in-out';
    document.body.style.opacity = '1';
  }, 100);
});

function enforceAuthGate() {
  const existing = localStorage.getItem('token');
  if (existing) return;
  const overlay = document.createElement('div');
  overlay.id = 'auth-overlay';
  overlay.className = 'modal-overlay';
  const modal = document.createElement('div');
  modal.className = 'modal-card';
  modal.innerHTML = `
    <h3 class="modal-title">欢迎使用农护宝</h3>
    <p class="modal-subtitle">请先登录或注册后继续使用全部功能</p>
    <div class="modal-tabs">
      <button id="tab-login" class="modal-tab active">登录</button>
      <button id="tab-register" class="modal-tab">注册</button>
    </div>
    <div id="auth-forms">
      <div id="form-login" class="modal-form">
        <input id="login-username" class="text-input" placeholder="用户名" />
        <input id="login-password" type="password" class="text-input" placeholder="密码" />
        <div class="action-buttons">
          <button id="do-login" class="action-button">登录</button>
        </div>
      </div>
      <div id="form-register" class="modal-form" style="display:none;">
        <input id="reg-username" class="text-input" placeholder="用户名" />
        <input id="reg-password" type="password" class="text-input" placeholder="密码" />
        <div class="action-buttons">
          <button id="do-register" class="action-button">注册</button>
        </div>
      </div>
    </div>
    <div id="auth-status" class="status-indicator"><span class="status-text">等待操作</span></div>
  `;
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  const toLogin = () => {
    document.getElementById('form-login').style.display = 'block';
    document.getElementById('form-register').style.display = 'none';
    document.getElementById('tab-login').classList.add('active');
    document.getElementById('tab-register').classList.remove('active');
  };
  const toRegister = () => {
    document.getElementById('form-login').style.display = 'none';
    document.getElementById('form-register').style.display = 'block';
    document.getElementById('tab-register').classList.add('active');
    document.getElementById('tab-login').classList.remove('active');
  };
  document.getElementById('tab-login').addEventListener('click', toLogin);
  document.getElementById('tab-register').addEventListener('click', toRegister);
  document.getElementById('do-login').addEventListener('click', async () => {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();
    if (!username || !password) { showStatus('auth-status', '请输入用户名和密码', 'error'); return; }
    try {
      const res = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      if (!res.ok) { const t = await res.text(); showStatus('auth-status', t || '登录失败', 'error'); return; }
      const data = await res.json();
      localStorage.setItem('token', data.token);
      showStatus('auth-status', '登录成功', 'success');
      setTimeout(()=>{ overlay.remove(); loadHistory(); }, 600);
    } catch (e) { showStatus('auth-status', '登录错误', 'error'); }
  });
  document.getElementById('do-register').addEventListener('click', async () => {
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value.trim();
    if (!username || !password) { showStatus('auth-status', '请输入用户名和密码', 'error'); return; }
    try {
      const res = await fetch('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      if (!res.ok) { const t = await res.text(); showStatus('auth-status', t || '注册失败', 'error'); return; }
      const data = await res.json();
      localStorage.setItem('token', data.token);
      showStatus('auth-status', '注册成功', 'success');
      setTimeout(()=>{ overlay.remove(); loadHistory(); }, 600);
    } catch (e) { showStatus('auth-status', '注册错误', 'error'); }
  });
}

// 添加平滑滚动
function smoothScrollTo(elementId) {
  const element = document.getElementById(elementId);
  if (element) {
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  }
}
function setupAuth() {
  const loginLink = document.getElementById('login-link');
  if (loginLink) {
    loginLink.addEventListener('click', async (e) => {
      e.preventDefault();
      const username = prompt('请输入用户名');
      if (!username) return;
      const password = prompt('请输入密码');
      if (!password) return;
      try {
        const res = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });
        if (!res.ok) {
          const t = await res.text();
          alert(t || '登录失败');
          return;
        }
        const data = await res.json();
        localStorage.setItem('token', data.token);
        alert('登录成功');
        loadHistory();
      } catch (err) {
        alert('登录错误');
      }
    });
  }
  const logoutLink = document.getElementById('logout-link');
  if (logoutLink) {
    logoutLink.addEventListener('click', (e) => {
      e.preventDefault();
      localStorage.removeItem('token');
      enforceAuthGate();
    });
  }
}

async function loadHistory() {
  const token = localStorage.getItem('token');
  if (!token) return;
  try {
    const res = await fetch('/diagnostics/history', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    const list = (data.history || []).slice().reverse().slice(0, 10);
    const html = list.map(item => `
      <div class="history-item">
        <div class="history-meta">
          <span>${new Date(item.time * 1000).toLocaleString()}</span>
          <span>${((item.confidence || 0) * 100).toFixed(1)}%</span>
        </div>
        <div class="history-body">
          <span class="crop-name">${item.crop || '-'}</span>
          <span class="disease-name">${item.disease || '-'}</span>
        </div>
      </div>
    `).join('');
    setHTML('history-content', html || '<p class="empty-subtext">暂无历史记录</p>');
  } catch (e) {}
}

function setupDiagnoseHistory() {
  const listEl = document.getElementById('history-content');
  const searchInput = document.getElementById('history-search-input');
  const searchBtn = document.getElementById('history-search-button');
  const insightsEl = document.getElementById('diagnose-insights');
  if (!listEl) return;
  const tk = localStorage.getItem('token');
  if (!tk) {
    showStatus('diagnose-history-status', '未登录', 'error');
    setHTML('history-content', '<p class="empty-subtext">请登录后查看历史诊断记录</p>');
    if (insightsEl) setHTML('diagnose-insights', '<p class="empty-subtext">登录后可生成诊断分析</p>');
    return;
  }
  const renderList = (items) => {
    const html = (items||[]).slice().reverse().map(item => {
      const conf = (((item.confidence||0)*100)||0).toFixed(1);
      const time = item.time ? new Date(item.time*1000).toLocaleString() : '-';
      const detail = item.report || {};
      const sym = detail.symptoms || detail['症状'] || '';
      const desc = detail.description || detail['描述'] || '';
      const prev = detail.prevention || detail['防治方法'] || '';
      return `
        <div class="kb-entry-card">
          <div class="kb-entry-header">
            <div>
              <h4 class="kb-entry-title">${item.crop || '-'} · ${item.disease || '-'}</h4>
              <p class="kb-hint">时间：${time} · 置信度：${conf}% · 标签：${item.label || '-'}</p>
            </div>
            <div class="kb-chips">${item.generated ? '<span class="kb-chip">AI补全</span>' : '<span class="kb-chip">知识库</span>'}</div>
          </div>
          <div class="kb-entry-body">
            <div class="kb-entry-section"><h5>症状</h5><p>${sym || '—'}</p></div>
            <div class="kb-entry-section"><h5>描述</h5><p>${desc || '—'}</p></div>
            <div class="kb-entry-section"><h5>防治方法</h5><p>${prev || '—'}</p></div>
          </div>
        </div>`;
    }).join('');
    setHTML('history-content', html || '<p class="empty-subtext">暂无历史记录</p>');
  };
  const loadAll = async () => {
    showStatus('diagnose-history-status', '正在加载...', 'loading');
    try {
      const res = await fetch('/diagnostics/history', { headers: { 'Authorization': `Bearer ${tk}` } });
      if (!res.ok) throw new Error('加载历史失败');
      const data = await res.json();
      renderList(data.history || []);
      showStatus('diagnose-history-status', '加载完成', 'success');
    } catch (e) {
      showStatus('diagnose-history-status', '加载失败', 'error');
    }
  };
  const doSearch = async () => {
    const q = (searchInput?.value || '').trim();
    showStatus('diagnose-history-status', '正在搜索...', 'loading');
    try {
      const res = await fetch(`/diagnostics/history/search?q=${encodeURIComponent(q)}`, { headers: { 'Authorization': `Bearer ${tk}` } });
      if (!res.ok) throw new Error('搜索失败');
      const data = await res.json();
      renderList(data.history || []);
      showStatus('diagnose-history-status', '搜索完成', 'success');
    } catch (e) {
      showStatus('diagnose-history-status', '搜索失败', 'error');
    }
  };
  if (searchBtn) searchBtn.addEventListener('click', doSearch);
  if (searchInput) searchInput.addEventListener('keydown', (e)=>{ if (e.key==='Enter') doSearch(); });
  loadAll();
  if (insightsEl) {
    showStatus('diagnose-insights-status', '正在分析...', 'loading');
    (async ()=>{
      try {
        const res = await fetch('/diagnostics/insights', { headers: { 'Authorization': `Bearer ${tk}` } });
        if (!res.ok) throw new Error('分析失败');
        const data = await res.json();
        const txt = (data.insights || '').replace(/\n/g,'<br/>');
        setHTML('diagnose-insights', `
          <div class="kb-report-card"><div class="kb-report-body"><div>${txt || '暂无分析'}</div></div></div>
        `);
        showStatus('diagnose-insights-status', '分析完成', 'success');
      } catch (e) {
        showStatus('diagnose-insights-status', '分析失败', 'error');
      }
    })();
  }
}

function setupCommunity() {
  const postForm = document.getElementById('post-form');
  const postsContainer = document.getElementById('posts-list');
  if (!postsContainer) return;
  const token = () => localStorage.getItem('token');
  const renderPostItem = (p) => `
    <div class="card" data-id="${p.id}">
      <div class="card-header">
        <h3 class="card-title">${p.title || '未命名'}</h3>
        <div class="status-indicator">
          <div class="status-icon info"></div>
          <span class="status-text">${p.author || '匿名'} · ${new Date(p.time*1000).toLocaleString()}</span>
        </div>
      </div>
      <div class="card-content">
        <p class="card-description">${(p.content||'').replace(/\n/g,'<br/>')}</p>
        <div class="card-features">${(p.tags||[]).map(t=>`<span class="feature-tag">${t}</span>`).join('')}</div>
      </div>
      <div class="answer-actions">
        <div class="action-buttons">
          <button class="action-button" data-action="toggle-comments">展开评论</button>
        </div>
        <div class="comments" id="comments-${p.id}" style="display:none;"></div>
        <div class="comment-form" id="comment-form-${p.id}" style="display:none; margin-top: var(--space-3);">
          <textarea class="text-input" rows="2" placeholder="写下你的评论..." id="comment-input-${p.id}"></textarea>
          <div class="action-buttons" style="margin-top: var(--space-2);">
            <button class="action-button" data-action="send-comment" data-id="${p.id}">发布评论</button>
          </div>
        </div>
      </div>
    </div>`;
  async function loadPosts() {
    try {
      const res = await fetch('/posts');
      if (!res.ok) return;
      const data = await res.json();
      const html = (data.posts||[]).map(renderPostItem).join('');
      setHTML('posts-list', html || '<p class="empty-subtext">暂无帖子</p>');
    } catch (e) {}
  }
  async function loadComments(postId) {
    try {
      const res = await fetch(`/posts/${postId}/comments`);
      if (!res.ok) return;
      const data = await res.json();
      const list = data.comments||[];
      const html = list.map(c=>`
        <div class="history-item">
          <div>
            <div class="history-meta">
              <span>${c.author || '匿名'}</span>
              <span>${new Date(c.time*1000).toLocaleString()}</span>
            </div>
            <div class="card-description" style="margin-top: var(--space-2);">${(c.content||'').replace(/\n/g,'<br/>')}</div>
          </div>
        </div>
      `).join('');
      setHTML(`comments-${postId}`, html || '<p class="empty-subtext">暂无评论</p>');
    } catch (e) {}
  }
  postsContainer.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const action = btn.getAttribute('data-action');
    if (action === 'toggle-comments') {
      const card = btn.closest('.card');
      const id = card?.getAttribute('data-id');
      const commentsEl = document.getElementById(`comments-${id}`);
      const formEl = document.getElementById(`comment-form-${id}`);
      if (!commentsEl || !id) return;
      const visible = commentsEl.style.display !== 'none';
      commentsEl.style.display = visible ? 'none' : 'block';
      formEl.style.display = visible ? 'none' : 'block';
      if (!visible) {
        await loadComments(id);
      }
    } else if (action === 'send-comment') {
      const id = btn.getAttribute('data-id');
      const content = document.getElementById(`comment-input-${id}`)?.value.trim();
      if (!content) return;
      const tk = token();
      if (!tk) { alert('请先登录'); return; }
      try {
        const res = await fetch(`/posts/${id}/comments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${tk}` },
          body: JSON.stringify({ content })
        });
        if (!res.ok) { const t = await res.text(); alert(t || '评论失败'); return; }
        await loadComments(id);
        document.getElementById(`comment-input-${id}`).value = '';
      } catch (err) {}
    }
  });
  if (postForm) {
    postForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = document.getElementById('post-title')?.value.trim();
      const content = document.getElementById('post-content')?.value.trim();
      const tags = document.getElementById('post-tags')?.value.trim().split(/[,\s]+/).filter(Boolean);
      if (!title || !content) { alert('标题和内容不能为空'); return; }
      const tk = token();
      if (!tk) { alert('请先登录'); return; }
      try {
        const res = await fetch('/posts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${tk}` },
          body: JSON.stringify({ title, content, tags })
        });
        if (!res.ok) { const t = await res.text(); alert(t || '发帖失败'); return; }
        await loadPosts();
        document.getElementById('post-title').value = '';
        document.getElementById('post-content').value = '';
        document.getElementById('post-tags').value = '';
      } catch (err) {}
    });
  }
  loadPosts();
}
