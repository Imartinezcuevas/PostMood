import React, { useState } from "react";
import logo from "../assets/postmood_v2.png";
import { motion, AnimatePresence } from "framer-motion";

const SearchPage = ({ onSearch, loading }) => {
  const [keyword, setKeyword] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (keyword.trim() !== "") onSearch(keyword);
  };

  return (
    <div className="search-container">
      <img src={logo} alt="PostMood" className="logo" />

      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Buscar..."
          className="search-input"
          disabled={loading}
        />

        <button type="submit" className="search-button" disabled={loading}>
          Analizar
        </button>
      </form>

      <AnimatePresence>
        {loading && (
          <motion.div
            className="loading-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              backgroundColor: "rgba(0,0,0,0.3)",
              zIndex: 1000,
            }}
          >
            <motion.div
              className="spinner"
              style={{
                width: 60,
                height: 60,
                border: "6px solid #fff",
                borderTopColor: "#ff5100ff",
                borderRadius: "50%",
                marginBottom: 16,
              }}
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
            />

            <p style={{ color: "#fff", fontSize: 18, fontWeight: "bold" }}>
              Analizando posts...
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SearchPage;
