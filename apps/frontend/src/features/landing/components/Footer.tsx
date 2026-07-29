import { ExternalLink, Github } from "lucide-react";

import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap">
        <div className="foot-grid">
          <div>
            <Logo />
            <p className="tag">Traceable proof of real engineering skill — not keyword-matched resumes.</p>
            <a className="foot-git" href="#" aria-label="GitHub repository (link coming soon)">
              <Github size={15} /> GitHub repository <ExternalLink size={12} />
            </a>
          </div>
          <div>
            <h5>Product</h5>
            <ul>
              <li>
                <a href="#how">How It Works</a>
              </li>
              <li>
                <a href="#product">Adaptive Interview</a>
              </li>
              <li>
                <a href="#evidence">Evidence Levels</a>
              </li>
              <li>
                <a href="#recruiter">Recruiter Workflow</a>
              </li>
            </ul>
          </div>
          <div>
            <h5>Team</h5>
            <ul>
              <li>
                Gaurav Yadav
                <div className="foot-role">
                  AI/ML & System Architecture ·{" "}
                  <a href="#" style={{ color: "var(--a1)" }}>
                    Portfolio ↗
                  </a>
                </div>
              </li>
              <li>
                Chetan Rawat
                <div className="foot-role">Backend</div>
              </li>
              <li>
                Kushlendra Singh
                <div className="foot-role">Frontend</div>
              </li>
              <li>
                Devesh Upadhya
                <div className="foot-role">Database & Deployment</div>
              </li>
            </ul>
          </div>
          <div>
            <h5>Project</h5>
            <ul>
              <li>Final-year B.Tech CSE capstone, Hindustan College of Science & Technology, 2026–27</li>
              <li>Top 3 — Smart India Hackathon 2025</li>
              <li>Project Guide: Mr. Diwakar Shrivastava</li>
            </ul>
          </div>
        </div>
        <div className="foot-bottom">
          <span>© 2026 GroundTruth AI — built as a final-year capstone project</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--faint)" }}>
            resumes claim · code proves
          </span>
        </div>
      </div>
    </footer>
  );
}
