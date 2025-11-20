import React from "react";
import SentimentChart from "../components/SentimentChart";
import PostCard from "../components/PostCard";
import "../index.css";

const ResultsPage = ({ results, onBack }) => {
  if (!results) return null;

  // Construir array plano de posts sin destruir IDs
  const posts = Object.entries(results).flatMap(([sentimentKey, data]) =>
    data.examples.map((example) => ({
      id: example.id,
      text: example.text,
      sentiment: sentimentKey,
      score: example.score,
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
            text={post.text}
            sentiment={post.sentiment}
            score={post.score}
          />
        ))}
      </div>
    </div>
  );
};

export default ResultsPage;
