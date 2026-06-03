/**
 * IntelliRAG — AI Service
 * 
 * Handles Ask AI, Mentor, Generate (flashcards, summary, slides), 
 * and Quiz API calls.
 */

const aiService = {
  /**
   * Ask a question across the user's document library.
   * @param {string} query
   * @param {string} userId
   * @param {string|null} docId - optional: restrict to one document
   * @param {string} llmVariant - '30b' | '105b'
   */
  async ask(query, userId, docId = null, llmVariant = '30b') {
    return window.api.post('/ask', {
      query,
      user_id: userId,
      doc_id: docId,
      llm_variant: llmVariant,
    });
  },

  /**
   * AI Mentor chat for a specific document.
   * @param {string} docId
   * @param {string} question
   * @param {Array} history - conversation history
   * @param {string} userId
   */
  async mentor(docId, question, history = [], userId = 'default_user') {
    return window.api.post('/mentor', {
      doc_id: docId,
      question,
      history,
      user_id: userId,
    });
  },

  /**
   * Generate educational content.
   * @param {string} docId
   * @param {string} contentType - 'flashcards' | 'summary' | 'slides' | 'fun_facts' | ...
   * @param {string} userId
   * @param {boolean} refresh
   */
  async generate(docId, contentType, userId, query = '', refresh = false, llmVariant = '30b') {
    return window.api.post('/generate', {
      doc_id: docId,
      content_type: contentType,
      user_id: userId,
      query,
      refresh,
      llm_variant: llmVariant,
    });
  },

  /**
   * Start a quiz for a document.
   * @param {string} docId
   * @param {string} quizType - 'quiz' | 'mock_test'
   * @param {string} userId
   */
  async startQuiz(docId, quizType = 'quiz', userId = 'default_user', llmVariant = '30b') {
    return window.api.post('/quiz/start', {
      doc_id: docId,
      quiz_type: quizType,
      user_id: userId,
      llm_variant: llmVariant,
    });
  },

  /**
   * Submit quiz answers for grading.
   * @param {string} docId
   * @param {string} userId
   * @param {Array} questions
   * @param {Array} answers
   * @param {string} quizType
   */
  async submitQuiz(docId, userId, questions, answers, quizType = 'quiz') {
    return window.api.post('/quiz/submit', {
      doc_id: docId,
      user_id: userId,
      questions,
      answers,
      quiz_type: quizType,
    });
  },
};

// Make globally available
window.aiService = aiService;
