import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { BattlePage } from '../pages/BattlePage';
import { saveCurrentSession } from '../services/sessionStore';
import { setActiveDemoScenarioId } from '../demo/demoState';
import { SCENARIO_1_SESSION } from '../demo/scenarios/scenario1_verified';
import { SCENARIO_2_SESSION } from '../demo/scenarios/scenario2_unresolved';
import { SCENARIO_3_SESSION } from '../demo/scenarios/scenario3_timeout';

describe('BattlePage (/battle)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.clearAllMocks();
    setActiveDemoScenarioId('fix_b_passes');
  });

  it('renders Left Panel ("UPLOADED QUERY") with language badge, question, and code', async () => {
    saveCurrentSession(SCENARIO_1_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_1_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('UPLOADED QUERY')).toBeInTheDocument();
    expect((await screen.findAllByText(/chunk_with_overlap/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/silently dropping the final 3 tokens/i)).toBeInTheDocument();
  });

  it('renders Right Panel with Stage Hero 5-step stepper and chess pieces', async () => {
    saveCurrentSession(SCENARIO_1_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_1_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('JUDGE AGENT')).toBeInTheDocument();
    expect(await screen.findByText('1. Ingest')).toBeInTheDocument();
    expect(await screen.findByText('2. Locate')).toBeInTheDocument();
    expect(await screen.findByText('3. Compare')).toBeInTheDocument();
    expect(await screen.findByText('4. Sandboxes')).toBeInTheDocument();
    expect(await screen.findByText('5. Adjudicate')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /skip animation/i })).toBeInTheDocument();
  });

  it('switches between Debate, Sandboxes, and Rounds tabs', async () => {
    saveCurrentSession(SCENARIO_1_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_1_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for initial load
    expect(await screen.findByText('JUDGE AGENT')).toBeInTheDocument();

    // Switch to Sandboxes tab
    const sandboxesTab = await screen.findByRole('tab', { name: /sandboxes/i });
    fireEvent.click(sandboxesTab);

    expect(await screen.findByText(/Sandbox A \(Fix A\)/i)).toBeInTheDocument();
    expect(await screen.findByText(/Sandbox B \(Fix B\)/i)).toBeInTheDocument();
    expect((await screen.findAllByText('DEMO DATA')).length).toBeGreaterThan(0);

    // Switch to Rounds tab
    const roundsTab = await screen.findByRole('tab', { name: /rounds/i });
    fireEvent.click(roundsTab);

    expect(await screen.findByText(/Adversarial Rounds Stepper/i)).toBeInTheDocument();
    expect(await screen.findByText(/Rejection Memory/i)).toBeInTheDocument();
  });

  it('fast-forwards stream immediately when Skip Animation button is clicked', async () => {
    saveCurrentSession(SCENARIO_1_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_1_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
          <Route path="/checkmate" element={<div>Navigated To Checkmate</div>} />
        </Routes>
      </MemoryRouter>
    );

    const skipBtn = await screen.findByRole('button', { name: /skip animation/i });
    fireEvent.click(skipBtn);

    // For verified scenario, fast-forwarding completed terminal event navigates to /checkmate
    await waitFor(() => {
      expect(screen.getByText('Navigated To Checkmate')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('stays on arena with working Retry and Back to home on Scenario 3 Watchdog Timeout', async () => {
    setActiveDemoScenarioId('sandbox_timeout');
    saveCurrentSession(SCENARIO_3_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_3_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
          <Route path="/" element={<div>Dashboard Home</div>} />
        </Routes>
      </MemoryRouter>
    );

    const skipBtn = await screen.findByRole('button', { name: /skip animation/i });
    fireEvent.click(skipBtn);

    // Watchdog timeout is execution_inconclusive -> must STAY on arena
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Watchdog Timeout/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Back to Home/i })).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('stays on arena with working Retry on Scenario 2 Unresolved', async () => {
    setActiveDemoScenarioId('round2_unresolved');
    saveCurrentSession(SCENARIO_2_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_2_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>
    );

    const skipBtn = await screen.findByRole('button', { name: /skip animation/i });
    fireEvent.click(skipBtn);

    // Unresolved -> must STAY on arena
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Bug Unresolved/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('collapses and expands failing test and error message sections', async () => {
    saveCurrentSession(SCENARIO_1_SESSION);

    render(
      <MemoryRouter initialEntries={[{ pathname: '/battle', state: { sessionId: SCENARIO_1_SESSION.id } }]}>
        <Routes>
          <Route path="/battle" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>
    );

    const toggleFailingTest = await screen.findByRole('button', { name: /failing test vector/i });
    expect(await screen.findByLabelText('Failing test vector code')).toBeInTheDocument();

    // Collapse
    fireEvent.click(toggleFailingTest);
    expect(screen.queryByLabelText('Failing test vector code')).not.toBeInTheDocument();

    // Re-expand
    fireEvent.click(toggleFailingTest);
    expect(await screen.findByLabelText('Failing test vector code')).toBeInTheDocument();
  });
});
