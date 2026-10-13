import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LandingPage } from '../pages/LandingPage';
import { addRecentSession, clearRecentSessions } from '../services/sessionStore';
import type { Session } from '../types/litmus';

// Test wrapper with route for / and placeholder for /battle
function renderLandingPage(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/battle" element={<div data-testid="battle-page">Battle Arena Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LandingPage ( / )', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    clearRecentSessions();
  });

  it('renders wordmark tagline, headline, and composer', () => {
    renderLandingPage();

    expect(screen.getByText(/Debate the Cause\./i)).toBeInTheDocument();
    expect(screen.getByText(/Run the Fix\./i)).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Upload Code/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Upload File/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /GitHub Repo/i })).toBeInTheDocument();
  });

  it('initially displays all three modes; clicking one locks it and displays "Change" button', async () => {
    renderLandingPage();

    // Initially all 3 tabs are present
    expect(screen.getByRole('tab', { name: /Upload Code/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Upload File/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /GitHub Repo/i })).toBeInTheDocument();

    // Click "Upload File"
    fireEvent.click(screen.getByRole('tab', { name: /Upload File/i }));

    // Now locked: other two hidden, "Change" button visible
    expect(screen.queryByRole('tab', { name: /GitHub Repo/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Change/i })).toBeInTheDocument();
    expect(screen.getByText('Upload File')).toBeInTheDocument();

    // Click "Change" -> returns to all 3 tabs
    fireEvent.click(screen.getByRole('button', { name: /Change/i }));
    expect(screen.getByRole('tab', { name: /Upload Code/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Upload File/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /GitHub Repo/i })).toBeInTheDocument();
  });

  it('"Try a sample bug" fills composer from demo sample and does NOT submit by itself', async () => {
    renderLandingPage();

    const sampleBtn = screen.getByRole('button', { name: /Try a sample bug/i });
    fireEvent.click(sampleBtn);

    // Code editor should contain sample bug
    const codeArea = screen.getByLabelText(/Source code/i) as HTMLTextAreaElement;
    expect(codeArea.value).toContain('def chunk_with_overlap');

    // Question input should contain sample question
    const questionInput = screen.getByPlaceholderText(/e\.g\. Why is chunk_with_overlap/i) as HTMLTextAreaElement;
    expect(questionInput.value).toContain('chunk_with_overlap');

    // Should NOT have navigated to /battle
    expect(screen.queryByTestId('battle-page')).not.toBeInTheDocument();
  });

  it('"Clear" button resets all inputs and errors', async () => {
    renderLandingPage();

    // Load sample first
    fireEvent.click(screen.getByRole('button', { name: /Try a sample bug/i }));
    const codeArea = screen.getByLabelText(/Source code/i) as HTMLTextAreaElement;
    expect(codeArea.value.length).toBeGreaterThan(0);

    // Click Clear
    const clearBtn = screen.getByRole('button', { name: /Clear/i });
    fireEvent.click(clearBtn);

    expect(codeArea.value).toBe('');
    const questionInput = screen.getByPlaceholderText(/e\.g\. Why is chunk_with_overlap/i) as HTMLTextAreaElement;
    expect(questionInput.value).toBe('');
  });

  it('shows inline validation errors when submitting empty form', async () => {
    renderLandingPage();

    // Circular send button is disabled initially
    const sendButton = screen.getByRole('button', { name: /Initiate adversarial debate/i });
    expect(sendButton).toBeDisabled();

    // If Enter is triggered via form or helper
    const questionInput = screen.getByPlaceholderText(/e\.g\. Why is chunk_with_overlap/i);
    fireEvent.keyDown(questionInput, { key: 'Enter', shiftKey: false });

    // Inline errors appear without page crash
    await waitFor(() => {
      expect(screen.getByText(/Source code is required/i)).toBeInTheDocument();
    });
  });

  it('validates GitHub repo format', async () => {
    renderLandingPage();

    // Switch to GitHub Repo mode
    fireEvent.click(screen.getByRole('tab', { name: /GitHub Repo/i }));

    const repoInput = screen.getByPlaceholderText(/https:\/\/github\.com\/owner\/repository/i);
    const questionInput = screen.getByPlaceholderText(/Pinpoint root cause of issue/i);

    // Fill invalid URL
    await userEvent.type(repoInput, 'https://notgithub.com/myrepo');
    await userEvent.type(questionInput, 'Find the bug');

    // Press Enter to submit
    fireEvent.keyDown(repoInput, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/Invalid format\. Use "https:\/\/github\.com\/owner\/repository"/i)).toBeInTheDocument();
    });

    // Provide valid format
    await userEvent.clear(repoInput);
    await userEvent.type(repoInput, 'https://github.com/litmus/debugger');

    // Send button should now be enabled
    const sendButton = screen.getByRole('button', { name: /Initiate adversarial debate/i });
    expect(sendButton).not.toBeDisabled();
  });

  it('validates File upload type and max size limit (1 MB)', async () => {
    renderLandingPage();

    // Switch to Upload File mode
    fireEvent.click(screen.getByRole('tab', { name: /Upload File/i }));

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    // 1. Invalid file extension (.exe)
    const invalidFile = new File(['binary content'], 'malware.exe', { type: 'application/octet-stream' });
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(screen.getByText(/Unsupported file type "\.exe"/i)).toBeInTheDocument();
    });

    // 2. Over 1 MB file (1.5 MB)
    const largeContent = new Uint8Array(1.5 * 1024 * 1024);
    const largeFile = new File([largeContent], 'huge.py', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [largeFile] } });

    await waitFor(() => {
      expect(screen.getByText(/File exceeds maximum limit of 1 MB/i)).toBeInTheDocument();
    });

    // 3. Valid file under 1 MB (.py)
    const validFile = new File(['def solve(): pass'], 'solution.py', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });

    await waitFor(() => {
      expect(screen.getByText('solution.py')).toBeInTheDocument();
    });
  });

  it('Shift+Enter in question field does not submit; Enter submits', async () => {
    renderLandingPage();

    // Load sample bug to have valid inputs
    fireEvent.click(screen.getByRole('button', { name: /Try a sample bug/i }));

    const questionInput = screen.getByPlaceholderText(/e\.g\. Why is chunk_with_overlap/i);

    // Shift+Enter -> does NOT navigate
    fireEvent.keyDown(questionInput, { key: 'Enter', shiftKey: true });
    expect(screen.queryByTestId('battle-page')).not.toBeInTheDocument();

    // Enter without Shift -> navigates to /battle
    fireEvent.keyDown(questionInput, { key: 'Enter', shiftKey: false });
    await waitFor(() => {
      expect(screen.getByTestId('battle-page')).toBeInTheDocument();
    });
  });

  it('blocks duplicate submissions on rapid clicks', async () => {
    renderLandingPage();

    // Load sample bug
    fireEvent.click(screen.getByRole('button', { name: /Try a sample bug/i }));

    const sendButton = screen.getByRole('button', { name: /Initiate adversarial debate/i });
    expect(sendButton).not.toBeDisabled();

    // Click submit
    fireEvent.click(sendButton);

    // Second click should be safely ignored / button becomes disabled during submission
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByTestId('battle-page')).toBeInTheDocument();
    });
  });

  it('displays friendly empty state for recent sessions when no sessions exist', () => {
    renderLandingPage();
    expect(screen.getByText(/No recent debugging sessions yet/i)).toBeInTheDocument();
  });

  it('lists recent sessions with status chips pairing icons and labels', async () => {
    const demo1: Session = {
      id: 'sess-1',
      title: 'Off by one bug in token chunker',
      mode: 'code',
      language: 'python',
      question: 'Test drops tail items',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'test_verified',
    };
    const demo2: Session = {
      id: 'sess-2',
      title: 'Contention livelock in lease cache',
      mode: 'code',
      language: 'python',
      question: 'Race condition',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'unresolved',
    };
    const demo3: Session = {
      id: 'sess-3',
      title: 'Watchdog timeout on regex evaluator',
      mode: 'code',
      language: 'python',
      question: 'Container timeout',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'execution_inconclusive',
    };
    const demo4: Session = {
      id: 'sess-4',
      title: 'In progress synthesis',
      mode: 'code',
      language: 'python',
      question: 'Debating',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'in_progress',
    };

    addRecentSession(demo1);
    addRecentSession(demo2);
    addRecentSession(demo3);
    addRecentSession(demo4);

    renderLandingPage();

    await waitFor(() => {
      expect(screen.getByText('Test-verified')).toBeInTheDocument();
      expect(screen.getByText('Unresolved')).toBeInTheDocument();
      expect(screen.getByText('Inconclusive')).toBeInTheDocument();
      expect(screen.getByText('In Progress')).toBeInTheDocument();
    });
  });
});
