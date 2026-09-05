// Ported from shelter-route-planner/frontend/src/components/Footer.jsx.
// Necessary adaptation: our backend has no `/shelters/stats`-equivalent
// endpoint, so the live shelter counter is dropped — the count below is a
// static number (matches db/seed/miklats_seed.json's total, updated
// manually rather than fetched). Links point at this project's own repo
// instead of the original's. CSS import removed: styles live in our
// combined index.css.

const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer">
      <div className="footer-content">
        <span className="footer-text">© {currentYear} Sasha Goldenberg · 12,640 shelters across Israel</span>
        <span className="footer-divider">·</span>
        <a
          href="https://maps.app.goo.gl/Kf5x3LqHqiKh4vPM6?g_st=ic"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-link"
        >
          Data Source
        </a>
        <span className="footer-divider">·</span>
        <a
          href="https://github.com/algoldenberg/miklat-devops"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-link"
        >
          GitHub
        </a>
        <span className="footer-divider">·</span>
        <span className="footer-license">MIT License</span>
      </div>
    </footer>
  );
};

export default Footer;
