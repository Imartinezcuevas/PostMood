import React, { useState } from "react";
import { motion } from "framer-motion";

const sentimentColors = {
  veryNegative: "#ff4d4d",
  negative: "#ff944d",
  positive: "#4da6ff",
  veryPositive: "#33cc33",
};

const spaToEng = {
  "Muy Negativo": "very negative",
  "Negativo": "negative",
  "Positivo": "positive",
  "Muy Positivo": "very positive",
};

const engToSpa = {
  "very negative": "Muy Negativo",
  "negative": "Negativo",
  "positive": "Positivo",
  "very positive": "Muy Positivo",
};

const PostCard = ({ id, text, sentiment, score, keyword, originalSentiment }) => {
  const [clicked, setClicked] = useState(false);
  const [selected, setSelected] = useState(null);

  const sendCorrection = async (corrected) => {
    if (clicked) return; // evita múltiples clicks
    setClicked(true);
    setSelected(corrected);

    try {
      const resp = await fetch("http://localhost:8000/correction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          post_id: id,
          keyword: keyword,
          original_sentiment: originalSentiment,
          corrected_sentiment: corrected,
          text: text,
          score: score
        }),
      });
      if (!resp.ok){
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err) {
      console.error("Error enviando corrección:", err);
      setClicked(false);
      setSelected(null);
    }
  };

  return (
    <motion.div
      className="post-card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <p className="post-text">{text[:256]}</p>

      {score !== undefined && (
        <p className="post-score">Sentimiento: {engToSpa[sentiment]}</p>
      )}

      <div className="post-card-buttons">
        {Object.keys(spaToEng).map((label) => {
          const key = spaToEng[label];
          const isSelected = selected === key;
          return (
            <button
              key={label}
              onClick={() => sendCorrection(key)}
              disabled={clicked}
              className={`correction-btn ${isSelected ? "selected " + key : ""}`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
};

export default PostCard;
