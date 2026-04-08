import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';
import { useState, useEffect, useRef } from 'react';
import { Upload, FileText, BarChart2, CheckCircle2, ChevronRight, X, Send, Database, Cog } from 'lucide-react';
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
  const [projectId, setProjectId] = useState(localStorage.getItem('projectId') || '');
  const [availableProjects, setAvailableProjects] = useState([]);
  const [modelId, setModelId] = useState('llama-3.3-70b-versatile');
  const [models, setModels] = useState(['llama-3.3-70b-versatile', 'gemma2-9b-it', 'mixtral-8x7b-32768']);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const [review, setReview] = useState({ ratings: {}, recommendations: [] });
  const [liveDocument, setLiveDocument] = useState('# No Architecture Document Found');
  const [constraints, setConstraints] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [selectedArtifacts, setSelectedArtifacts] = useState([]);

  const [activeTab, setActiveTab] = useState('review'); // 'review' | 'document'
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Fetch available models
    fetch(`${API_BASE_URL}/api/models`)
      .then(res => res.json())
      .then(data => {
        if (data.models && data.models.length > 0) {
          setModels(data.models);
        }
      })
      .catch(err => console.error("Could not load models"));

    // Fetch existing projects
    fetch(`${API_BASE_URL}/api/projects`)
      .then(res => res.json())
      .then(data => {
        if (data.projects) {
          setAvailableProjects(data.projects);
          // Auto-select if nothing in local storage but projects exist
          if (!localStorage.getItem('projectId') && data.projects.length > 0) {
            setProjectId(data.projects[0]);
          }
        }
      })
      .catch(err => console.error("Could not load projects"));
  }, []);

  useEffect(() => {
    if (projectId) {
      localStorage.setItem('projectId', projectId);
      fetchProjectState(projectId);
    }
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleNewProject = () => {
    const freshId = 'PROJ-' + Math.random().toString(36).substr(2, 9).toUpperCase();
    setProjectId(freshId);
    setReview({ ratings: {}, recommendations: [] });
    setLiveDocument('# New Architecture Document\n\nPlease upload an architecture PDF or start describing your system to begin.');
    setConstraints([]);
    setArtifacts([]);
    setSelectedArtifacts([]);
    setMessages([{ role: 'system', content: `Started new project workspace: ${freshId}` }]);
    localStorage.setItem('projectId', freshId);
    
    if (!availableProjects.includes(freshId)) {
      setAvailableProjects([freshId, ...availableProjects]);
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
        // By default, select all retrieved artifacts if we haven't manipulated selection manually
        setSelectedArtifacts(fetchedArtifacts.map(a => a.pdf_id));

        if (data.running_summary) {
          setMessages([{ role: 'system', content: `*Context Recovered:*\n\n${data.running_summary}` }]);
        } else {
          setMessages([{ role: 'system', content: `Workspace connected.` }]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch project state");
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
          history: messages,
          model_id: modelId,
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
                 method: 'POST'
             });
         } catch (e) {
             console.error("Evaluation trigger failed", e);
         }
         setIsCalculating(false);
         fetchProjectState(projectId);
      }

    } catch (error) {
      console.error("Chat Error:", error);
      setMessages(prev => [...prev, { role: 'system', content: 'Connection Error to Backend.' }]);
    } finally {
      setIsLoading(false);
    }
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

        <div className="settings-panel">
          <div className="input-group">
            <label>Current Project</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select 
                value={projectId} 
                onChange={e => {
                  setProjectId(e.target.value);
                  setMessages([]);
                }}
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
              <button 
                onClick={handleNewProject}
                style={{
                  background: 'var(--accent-primary)',
                  border: 'none',
                  color: 'white',
                  padding: '0 12px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600
                }}
                title="Create New Project"
              >
                New
              </button>
            </div>
          </div>

          <div className="input-group">
            <label>Language Model</label>
            <select value={modelId} onChange={e => setModelId(e.target.value)}>
              {models.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
          <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf" hidden />
          <Upload size={32} />
          <p>{isUploading ? "Processing..." : "Upload Architecture (PDF)"}</p>
        </div>

        <div className="artifacts-panel">
          <h3>Project Artefacts</h3>
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

        {constraints.length > 0 && (
          <div className="constraints-panel">
            <h3>Active Constraints</h3>
            <ul>
              {constraints.map((c, i) => (
                <li key={i}>
                  <CheckCircle2 size={14} className="icon-success" />
                  <span>{c.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      <section className="chat-panel">
        <div className="chat-header">
          <h3>Architecture Copilot</h3>
        </div>
        
        <div className="chat-interface">
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                <Cog className="spin-slow" size={48} />
                <p>Upload a document or ask a question to begin refining your architecture.</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.role}`}>
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown components={MarkdownComponents}>{msg.content}</ReactMarkdown>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                  {msg.system_updates && (
                    <div className="system-updates">
                      {msg.system_updates.map((update, i) => (
                        <span key={i} className="update-badge">✓ {update}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            {isLoading && <div className="message assistant loading">Typing...</div>}
            <div ref={messagesEndRef} />
          </div>
          
          <div className="prompt-pills">
            {["@LiveDocumentation restructure to standard template", "@LiveDocumentation add missing microservices", "@LiveDocumentation enforce secure zero trust", "@LiveDocumentation migrate to AWS native"].map((pt, i) => (
              <button key={i} className="pill-btn" onClick={() => setInput(pt)}>{pt}</button>
            ))}
          </div>

          <div className="chat-input-area">
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Discuss or ask Copilot to redesign using @LiveDocumentation..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button onClick={sendMessage} disabled={isLoading || !input.trim() || !projectId}>
              <Send size={18} />
            </button>
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
              {isCalculating && <div className="calculating-overlay"><div className="spinner"></div><h2>Evaluating Architecture...</h2></div>}
              <div className="review-summary">
                <h3>Problem Statement</h3>
                <p>{review.problem_statement || "N/A"}</p>
                <h3>Architectural Overview</h3>
                <p>{review.overview || "N/A"}</p>
              </div>

              {Object.keys(review.ratings || {}).length > 0 ? (
                <>
                  {renderRatings()}
                  <div className="recommendations-box">
                    <h4>Key Recommendations</h4>
                    {Array.isArray(review.recommendations) ? review.recommendations.map((rec, idx) => (
                      <li key={idx} className="recommendation-card">
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
            <div className="document-tab markdown-body">
              <ReactMarkdown components={MarkdownComponents}>{liveDocument}</ReactMarkdown>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default App;