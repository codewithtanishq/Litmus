import { Composer } from '../components/composer/Composer';
import { RecentSessions } from '../components/recent/RecentSessions';
import './LandingPage.css';

export const LandingPage = () => {
  return (
    <main className="litmus-landing-page" id="main-content">
      {/* Looping Atmospheric Background Video */}
      <div className="litmus-video-bg-container" aria-hidden="true">
        <video
          className="litmus-video-bg"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          src="/dashboard_video.mp4"
        >
          <source src="/dashboard_video.mp4" type="video/mp4" />
          <source src="/gemini_generated_video_c146a041.mp4" type="video/mp4" />
        </video>
      </div>

      <div className="litmus-landing-content">
        {/* Editorial Headline & Tagline Section (Inspired by Image 3 layout) */}
        <section className="litmus-hero" aria-labelledby="hero-headline">
          <h1 id="hero-headline" className="litmus-hero__title">
            Debate the Cause. <br />
            <span className="litmus-hero__title-italic">Run the Fix.</span>
          </h1>

          <p className="litmus-hero__subtitle">
            Debate bugs with adversarial multi-agent reasoning. Ephemeral test sandboxes decide on empirical evidence.
          </p>
        </section>

        {/* Centered Clean Composer Box */}
        <section className="litmus-composer-section" aria-label="Input Composer">
          <Composer />
        </section>

        {/* Recent Sessions / History Section */}
        <section 
          id="recent-sessions-anchor" 
          className="litmus-recents-section" 
          aria-label="Recent Debugging Sessions"
        >
          <RecentSessions />
        </section>
      </div>
    </main>
  );
};
