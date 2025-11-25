import React from "react";
import SentimentChart from "../components/SentimentChart";
import PostCard from "../components/PostCard";
import "../index.css";

const ResultsPage = ({ results, onBack }) => {
  if (!results) return null;

  // Construir array plano de posts sin destruir IDs
  const posts = Object.entries(results).flatMap(([sentimentKey, data]) =>
    data.examples.map((example) => ({
      id: example.id || example.post_id,
      post_id: example.post_id || example.id,
      text: example.text,
      title: example.title,
      full_text: example.full_text,
      sentiment: example.label,
      originalSentiment: example.label,
      score: example.score,
      keyword: example.keyword,
      url: example.url,
    }))
  );

  return (
    <div className="results-page">
      <div className="header-bar">
        <button className="back-button" onClick={onBack}>
          ← Volver
        </button>
      </div>

      <SentimentChart data={results} />

      <div className="posts-grid">
        {posts.map((post) => (
          <PostCard
            key={post.id}
            id={post.id}
            text={post.full_text}
            sentiment={post.sentiment}
            originalSentiment={post.originalSentiment}
            score={post.score}
            keyword={post.keyword}
          />
        ))}
      </div>
    </div>
  );
};

export default ResultsPage;
