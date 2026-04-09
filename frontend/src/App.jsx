import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';
import { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  Settings, 
  FileText, 
  Bot, 
  Download, 
  CheckCircle2, 
  AlertCircle, 
  FileCheck, 
  Zap, 
  History, 
  Layout, 
  Layers, 
  MessageSquare, 
  Eye, 
  ArrowRight, 
  Cog,
  User,
  CloudOff,
  Send,
  BarChart2,
  Database,
  Trash2,
  Info
} from 'lucide-react';
import './App.css';

// Initialize Mermaid for Enterprise Dark Theme
mermaid.initialize({
  startOnLoad: true,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'Inter, sans-serif'
});

const Mermaid = ({ chart }) => {
  const ref = useRef(null);
  const [svg, setSvg] = useState('');

  useEffect(() => {
    const render = async () => {
      if (ref.current && chart) {
        try {
           // Generate a unique ID for each chart
           const id = 'mermaid-' + Math.random().toString(36).substr(2, 9);
           const { svg } = await mermaid.render(id, chart);
           setSvg(svg);
        } catch (e) {
          console.error("Mermaid error:", e);
        }
      }
    };
    render();
  }, [chart]);

  return <div ref={ref} className="mermaid" dangerouslySetInnerHTML={{ __html: svg }} />;
};

const MarkdownComponents = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-mermaid/.exec(className || '');
    return !inline && match ? (
      <Mermaid chart={String(children).replace(/\n$/, '')} />
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [projectId, setProjectId] = useState('');
  const [availableProjects, setAvailableProjects] = useState([]);
  const [providerId, setProviderId] = useState(() => (localStorage.getItem('providerId') || 'groq').toLowerCase());
  const [modelId, setModelId] = useState(() => localStorage.getItem('modelId') || 'llama-3.3-70b-versatile');
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [isModelsLoading, setIsModelsLoading] = useState(false);
  const [isProjectCreated, setIsProjectCreated] = useState(false);
  const [sidebarTab, setSidebarTab] = useState('workspace'); // 'workspace' | 'artefacts'
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  // Mentions State
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const mentionOptions = ['@LiveDocumentation', '@ReviewDocumentation'];
  
  const [review, setReview] = useState({ ratings: {}, recommendations: [] });
  const [liveDocument, setLiveDocument] = useState('# No Architecture Document Found');
  const [constraints, setConstraints] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [selectedArtifacts, setSelectedArtifacts] = useState([]);

  const [activeTab, setActiveTab] = useState('review'); // 'review' | 'document'
  const [runningSummary, setRunningSummary] = useState('');
  const fileInputRef = useRef(null);
  const chatMessagesRef = useRef(null);

  const highlightTags = (strText, isOverlay = false) => {
    if (!strText) return null;
    const parts = strText.split(/(@(?:LiveDocumentation|ReviewDocumentation))/g);
    return parts.map((part, index) => {
      if (part === '@LiveDocumentation' || part === '@ReviewDocumentation') {
        return <span key={index} className={isOverlay ? "tag-highlight" : "msg-tag"}>{part}</span>;
      }
      return part;
    });
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    
    // Check for mentions
    const cursorPosition = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPosition);
    const match = textBeforeCursor.match(/@(\w*)$/);
    
    if (match) {
      setShowMentions(true);
      setMentionFilter(match[1].toLowerCase());
    } else {
      setShowMentions(false);
    }
  };

  const insertMention = (tag) => {
    const cursorPosition = input.lastIndexOf('@');
    if (cursorPosition !== -1) {
      const newInput = input.substring(0, cursorPosition) + tag + ' ' + input.substring(input.length);
      setInput(newInput);
    } else {
      setInput(input + tag + ' ');
    }
    setShowMentions(false);
  };

  const fetchModelsForProvider = async (pid) => {
    setIsModelsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/models/${pid}`);
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        setModels(data.models);
        // Only auto-select if current modelId is not in the new list
        if (!data.models.find(m => m.id === modelId)) {
          setModelId(data.models[0].id);
        }
      }
    } catch (e) {
      console.error("Error fetching models", e);
    }
    setIsModelsLoading(false);
  };

  useEffect(() => {
    // Fetch available providers
    fetch(`${API_BASE_URL}/api/models`)
      .then(res => res.json())
      .then(data => {
        if (data.providers) {
          setProviders(data.providers);
          // Fetch initial models for the current providerId
          fetchModelsForProvider(providerId);
        }
      })
      .catch(err => console.error("Could not load providers"));

    // Fetch existing projects
    fetch(`${API_BASE_URL}/api/projects`)
      .then(res => res.json())
      .then(data => {
        if (data.projects) {
          setAvailableProjects(data.projects);
          // Only populate list, do NOT auto-select on refresh - strict policy
          setIsProjectCreated(false);
          setProjectId('');
        }
      })
      .catch(err => console.error("Could not load projects"));
  }, []);

  useEffect(() => {
    if (projectId) {
      localStorage.setItem('projectId', projectId);
      // Check if project exists and hydrate
      fetchProjectState(projectId);
      setIsProjectCreated(true);
    } else {
      setIsProjectCreated(false);
    }
  }, [projectId]);

  // PERSIST SETTINGS ON CHANGE
  useEffect(() => {
    if (modelId) localStorage.setItem('modelId', modelId);
  }, [modelId]);

  useEffect(() => {
    if (providerId) localStorage.setItem('providerId', providerId);
  }, [providerId]);

  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
    }
  }, [messages]);

  const handleNewProject = async () => {
    const freshId = 'PROJ-' + Math.random().toString(36).substr(2, 9).toUpperCase();
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/project`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: freshId })
      });
      const data = await res.json();
      
      if (data.status === 'created' || data.status === 'exists') {
        setProjectId(freshId);
        setIsProjectCreated(true);
        setReview({ ratings: {}, recommendations: [] });
        setLiveDocument('# New Architecture Document\n\nPlease upload an architecture PDF or start describing your system to begin.');
        setConstraints([]);
        setArtifacts([]);
        setSelectedArtifacts([]);
        setMessages([{ role: 'system', content: `Workspace initialized for project ${freshId}.` }]);
        
        if (!availableProjects.includes(freshId)) {
          setAvailableProjects([freshId, ...availableProjects]);
        }
      }
    } catch (err) {
      console.error("Failed to create project:", err);
    }
  };

  const fetchProjectState = async (pid) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/project/${pid}`);
      if (res.ok) {
        const data = await res.json();
        setReview({
          ratings: data.review?.ratings || {},
          recommendations: data.review?.recommendations || [],
          problem_statement: data.review?.problem_statement || "",
          overview: data.review?.overview || ""
        });
        setLiveDocument(data.live_document || '# No Data');
        setConstraints(data.constraints || []);
        
        const fetchedArtifacts = data.artifacts || [];
        setArtifacts(fetchedArtifacts);
        setSelectedArtifacts(fetchedArtifacts.map(a => a.pdf_id));

        // Hydrate History and Pinned Summary
        if (data.history && data.history.length > 0) {
          setMessages(data.history);
        } else {
          setMessages([{ role: 'system', content: `Workspace initialized for project ${pid}. Upload architecture to begin.` }]);
        }

        setRunningSummary(data.running_summary || '');
      }
    } catch (e) {
      console.error("Failed to fetch project state");
    }
  };

  const handleDeleteProject = async () => {
    if (!projectId) return;
    if (!window.confirm(`Are you sure you want to delete Project ${projectId}? This action is permanent and will wipe all associated architectural data.`)) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/project/${projectId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        const remaining = availableProjects.filter(id => id !== projectId);
        setAvailableProjects(remaining);
        if (remaining.length > 0) {
          setProjectId(remaining[0]);
        } else {
          handleNewProject();
        }
      } else {
        alert("Failed to delete project.");
      }
    } catch (err) {
      console.error("Delete Project Error:", err);
      alert("Error deleting project.");
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const newProjectId = projectId || 'PROJ-' + Math.random().toString(36).substr(2, 9).toUpperCase();
    if (!projectId) {
      setProjectId(newProjectId);
      if (!availableProjects.includes(newProjectId)) {
        setAvailableProjects([newProjectId, ...availableProjects]);
      }
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', newProjectId);
    formData.append('provider', providerId);
    formData.append('model_id', modelId);

    try {
      const res = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      setProjectId(data.project_id);
      
      // Post-upload fetch State
      await fetchProjectState(data.project_id);

      setMessages(prev => [...prev, {
        role: 'system',
        content: `Uploaded ${file.name}. Architecture baseline and review initialized.`
      }]);
    } catch (err) {
      alert("Error Uploading File.");
    } finally {
      setIsUploading(false);
      e.target.value = null;
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !projectId) return;

    const newHistory = [...messages, { role: 'user', content: input }];
    setMessages(newHistory);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          project_id: projectId,
          message: input, 
          history: messages.slice(-10),
          model_id: modelId,
          provider: providerId,
          pdf_ids: selectedArtifacts
        }),
      });

      if (!response.ok) throw new Error('API Error');

      const data = await response.json();
      
      const assistantMessage = { role: 'assistant', content: data.content };
      if (data.system_updates && data.system_updates.length > 0) {
        assistantMessage.system_updates = data.system_updates;
      }
      
      setMessages(prev => [...prev, assistantMessage]);

      if (data.system_updates && data.system_updates.length > 0) {
         setIsCalculating(true);
          try {
              await fetch(`${API_BASE_URL}/api/project/${projectId}/evaluate`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                      provider: providerId,
                      model_id: modelId
                  })
              });
          } catch (e) {
             console.error("Evaluation trigger failed", e);
         }
         setIsCalculating(false);
         fetchProjectState(projectId);
      }

    } catch (error) {
      console.error("Chat Error:", error);
      setMessages(prev => [...prev, { role: 'system', content: 'Connection Error to Backend.', isError: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportMarkdown = () => {
    const blob = new Blob([liveDocument], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Architecture-Document-${projectId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportPDF = () => {
    window.print();
  };

  const renderRatings = () => {
    const merged = review.ratings || {};

    return (
      <div className="ratings-grid">
        {Object.entries(merged).map(([key, val]) => {
          const score = (typeof val === 'object' && val !== null) ? val.score : val;
          const rationale = (typeof val === 'object' && val !== null) ? val.rationale : null;

          return (
            <div key={key} className="rating-item">
              <div className="rating-header">
                <span className="rating-label">{key}</span>
                <span className="rating-score">{score}/10</span>
              </div>
              <div className="rating-bar-bg">
                <div className="rating-bar-fill" style={{ width: `${score * 10}%` }}></div>
              </div>
              {rationale && (
                <details className="rating-rationale">
                  <summary>View Rationale</summary>
                  <p>{rationale}</p>
                </details>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <Database className="brand-icon" />
          <h2>ArchReview AI</h2>
        </div>

        <div className="sidebar-nav">
          <button 
            className={`sidebar-nav-item ${sidebarTab === 'workspace' ? 'active' : ''}`}
            onClick={() => setSidebarTab('workspace')}
          >
            <Layout size={16} /> Workspace
          </button>
          <button 
            className={`sidebar-nav-item ${sidebarTab === 'artefacts' ? 'active' : ''}`}
            onClick={() => setSidebarTab('artefacts')}
          >
            <Layers size={16} /> Artefacts
          </button>
        </div>

        <div className="sidebar-content">
          {sidebarTab === 'workspace' && (
            <>
              <div className="settings-panel">
                <div className="input-group">
                  <label>Current Project</label>
                  <div className="project-header">
                    <select 
                      value={projectId} 
                      onChange={e => setProjectId(e.target.value)}
                      style={{ flex: 1 }}
                    >
                      {projectId && !availableProjects.includes(projectId) && (
                        <option value={projectId}>{projectId}</option>
                      )}
                      <option value="" disabled>Select a project...</option>
                      {availableProjects.map(pid => (
                        <option key={pid} value={pid}>{pid}</option>
                      ))}
                    </select>
                  </div>
                  <div className="project-button-stack">
                    <button 
                      onClick={handleNewProject}
                      className="action-btn-wide"
                      title="Create New Project"
                    >
                      Create New Project
                    </button>
                    <button 
                      onClick={handleDeleteProject}
                      className="delete-project-btn-wide"
                      title="Delete Current Project"
                      disabled={!projectId}
                    >
                      <Trash2 size={16} /> Delete Project
                    </button>
                  </div>
                </div>

                <div className="dual-dropdown-group">
                  <div className="input-group">
                    <label>Provider</label>
                    <select value={providerId} onChange={e => {
                      const pid = e.target.value;
                      setProviderId(pid);
                      fetchModelsForProvider(pid);
                    }}>
                      {providers.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="input-group">
                    <label>Model</label>
                    <select value={modelId} onChange={e => setModelId(e.target.value)} disabled={isModelsLoading}>
                      {isModelsLoading ? (
                        <option>Fetching models...</option>
                      ) : (
                        models.map(m => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))
                      )}
                    </select>
                  </div>
                </div>
              </div>

              <div 
                className={`upload-zone ${!isProjectCreated ? 'zone-disabled' : ''}`} 
                onClick={() => isProjectCreated && fileInputRef.current?.click()}
              >
                <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf" hidden />
                <Upload size={32} />
                <p>{isUploading ? "Processing..." : isProjectCreated ? "Upload Architecture (PDF)" : "Create a project to upload"}</p>
              </div>
            </>
          )}

          {sidebarTab === 'artefacts' && (
            <div className="artifacts-panel">
              <div className="panel-header">
                <h3>Project Artefacts</h3>
              </div>
              {artifacts.length === 0 ? (
                <p className="empty-artifacts">No artefact is uploaded. You can upload a design or start completely from scratch.</p>
              ) : (
                <div className="artifacts-list">
                  <label className="artifact-checkbox select-all">
                    <input 
                      type="checkbox" 
                      checked={selectedArtifacts.length === artifacts.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedArtifacts(artifacts.map(a => a.pdf_id));
                        } else {
                          setSelectedArtifacts([]);
                        }
                      }}
                    />
                    <span className="truncate">Select All</span>
                  </label>
                  {artifacts.map((art) => (
                    <label key={art.pdf_id} className="artifact-checkbox">
                      <input 
                        type="checkbox" 
                        checked={selectedArtifacts.includes(art.pdf_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedArtifacts([...selectedArtifacts, art.pdf_id]);
                          } else {
                            setSelectedArtifacts(selectedArtifacts.filter(id => id !== art.pdf_id));
                          }
                        }}
                      />
                      <span className="truncate" title={art.filename}>{art.filename}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>


      </aside>

      <section className="chat-panel">
        <div className="chat-header">
          <h3>Architecture Copilot</h3>
        </div>
        
        <div className="chat-interface">
          {runningSummary && (
            <div className="pinned-summary">
              <h4><Info size={14} /> Project Running Summary</h4>
              <div className="markdown-body">
                <ReactMarkdown>{runningSummary}</ReactMarkdown>
              </div>
            </div>
          )}
          <div className="chat-messages" ref={chatMessagesRef}>
            {messages.length === 0 ? (
              <div className="empty-state">
                <Cog className="spin-slow" size={48} />
                <p>Upload a document or ask a question to begin refining your architecture.</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`message-wrapper ${msg.role}`}>
                  <div className="message-icon">
                    {msg.role === 'user' ? <User size={18} /> : 
                     msg.role === 'system' ? (msg.isError ? <CloudOff size={18} className="icon-error" /> : <Database size={18} style={{color: '#94a3b8'}} />) : 
                     <Bot size={18} />}
                  </div>
                  <div className="message-bubble">
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown components={MarkdownComponents}>{msg.content}</ReactMarkdown>
                    ) : (
                      <p style={{ margin: 0 }}>{highlightTags(msg.content, false)}</p>
                    )}
                    {msg.system_updates && (
                      <div className="system-updates">
                        {msg.system_updates.map((update, i) => (
                          <span key={i} className="update-badge"> {update}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && <div className="message assistant loading">Typing...</div>}
          </div>
          
          <div className="chat-input-wrapper">
            <div className={`prompt-pills ${!isProjectCreated ? 'zone-disabled' : ''}`}>
              {[
                "@ReviewDocumentation: Identify Gaps & Risks",
                "@ReviewDocumentation: Analyze Scalability",
                "@LiveDocumentation: Refine Technical English",
                "@LiveDocumentation: Restructure to SAD (arc42)"
              ].map((pt, i) => (
                <button 
                  key={i} 
                  className="pill-btn" 
                  disabled={!isProjectCreated}
                  onClick={() => {
                    if (!isProjectCreated) return;
                    const tag = pt.replace(':', '');
                    setInput(tag + " ");
                  }}
                >
                  {pt}
                </button>
              ))}
            </div>

            <div className="chat-input-area">
              {showMentions && (
                <div className="mentions-popup">
                  {mentionOptions
                    .filter(opt => opt.toLowerCase().includes(mentionFilter))
                    .map((opt, idx) => (
                      <div key={idx} className="mention-item" onClick={() => insertMention(opt)}>
                        {opt}
                      </div>
                  ))}
                  {mentionOptions.filter(opt => opt.toLowerCase().includes(mentionFilter)).length === 0 && (
                    <div className="mention-item" style={{color: '#94a3b8', cursor: 'default'}}>No match</div>
                  )}
                </div>
              )}
              
              <div className={`input-with-highlight ${!isProjectCreated ? 'zone-disabled' : ''}`}>
                <div className="highlighter-overlay">{highlightTags(input, true)}</div>
                <textarea 
                  value={input}
                  onChange={handleInputChange}
                  disabled={!isProjectCreated || isLoading}
                  placeholder={isProjectCreated ? "Discuss or ask Copilot to redesign using @LiveDocumentation..." : "Select or create a project to start chatting..."}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && isProjectCreated) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                />
              </div>
              <button className="send-btn" onClick={sendMessage} disabled={isLoading || !input.trim() || !isProjectCreated}>
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="workspace-panel">
        <div className="tabs">
          <button 
            className={activeTab === 'review' ? 'active' : ''} 
            onClick={() => setActiveTab('review')}
          >
            <BarChart2 size={16} /> Diagnostic Review
          </button>
          <button 
            className={activeTab === 'document' ? 'active' : ''} 
            onClick={() => setActiveTab('document')}
          >
            <FileText size={16} /> Live Document
          </button>
        </div>

        <div className="workspace-content">
          {activeTab === 'review' && (
            <div className="review-tab">
              <div className="review-header">
                <h3>Live Diagnosis</h3>
                <button 
                  className={`diag-btn-tiny ${isCalculating ? 'loading' : ''}`}
                  onClick={async () => {
                    if (!projectId) return;
                    setIsCalculating(true);
                    try {
                      await fetch(`${API_BASE_URL}/api/project/${projectId}/evaluate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider: providerId, model_id: modelId })
                      });
                      await fetchProjectState(projectId);
                    } catch (e) {
                      console.error("Manual evaluation failed", e);
                    }
                    setIsCalculating(false);
                  }}
                  disabled={!projectId || isCalculating}
                >
                  <Zap size={14} /> {isCalculating ? "Evaluating..." : "Run Diagnostic"}
                </button>
              </div>

              {isCalculating && (
                <div className="calculating-overlay">
                  <Cog className="spin-slow" size={48} />
                  <p style={{ marginTop: '16px', fontWeight: '500' }}>Evaluating Design Updates...</p>
                </div>
              )}
              <div className="review-indented-content">
                <div className="review-section">
                  <h4>Problem Statement</h4>
                  <p>{review.problem_statement || "N/A"}</p>
                </div>
                
                <div className="review-section">
                  <h4>Architectural Overview</h4>
                  <p>{review.overview || "N/A"}</p>
                </div>
              </div>

              {Object.keys(review.ratings || {}).length > 0 ? (
                <>
                  {renderRatings()}
                  <div className="recommendations-box">
                    <h4>Key Recommendations</h4>
                    {Array.isArray(review.recommendations) ? review.recommendations.map((rec, idx) => (
                      <li key={idx} className="recommendation-card" style={{ listStyle: 'none' }}>
                        <div className="rec-header">
                           <strong>{rec.title || rec.category || "Recommendation"}</strong>
                        </div>
                        <p className="rec-detail">{rec.detail || rec.text}</p>
                        {rec.why_it_fits && <p className="rec-why"><em>Why it fits:</em> {rec.why_it_fits}</p>}
                        <button 
                          className="apply-rec-btn"
                          onClick={() => setInput(`@LiveDocumentation Please apply this recommendation: ${rec.title || rec.category}. ${rec.detail || rec.text}`)}
                        >
                          Apply to Document
                        </button>
                      </li>
                    )) : <p>No recommendations generated.</p>}
                  </div>
                </>
              ) : (
                <p className="no-data">No review available yet. Please upload a PDF to generate a diagnostic.</p>
              )}
            </div>
          )}

          {activeTab === 'document' && (
            <div className="document-tab">
              <div className="export-controls" style={{ 
                display: 'flex', 
                justifyContent: 'flex-end', 
                gap: '10px', 
                marginBottom: '20px' 
              }}>
                <button onClick={handleExportMarkdown} className="pill-btn" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Download size={14} /> Export .md
                </button>
                <button onClick={handleExportPDF} className="pill-btn" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FileText size={14} /> Export PDF
                </button>
              </div>

              <div className="markdown-body">
                <ReactMarkdown components={MarkdownComponents}>{liveDocument}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default App;