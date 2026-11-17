"use client";

import { useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState } from "react";
import { envoyer, type Population } from "@/lib/api";
import { avecPopulation } from "@/lib/format";
import { IconeFermer, Logo } from "./Icones";

interface Reponse {
  reponse: string;
  sources: string[];
  liens: { pcode: string; province: string }[];
  mode: "gemini" | "hors ligne";
}

type Message = { auteur: "moi"; texte: string } | ({ auteur: "sentinelle" } & Reponse);

const SUGGESTIONS = [
  "Où agir en priorité en 2025-2026 ?",
  "Quelles provinces risquent une rupture ?",
  "Compare Loroum et Yagha",
  "Que se passe-t-il dans la région Soum ?",
  "Quelles provinces résistent ?",
  "Où les filles sont-elles plus exposées ?",
];

/** Texte de réponse : lignes, puces « - » et gras « **…** », sans interpréter de HTML. */
function Texte({ texte }: { texte: string }) {
  return (
    <>
      {texte.split("\n").map((ligne, i) => {
        const puce = /^\s*[-•]\s+/.test(ligne);
        const contenu = ligne.replace(/^\s*[-•]\s+/, "");
        const morceaux = contenu.split(/(\*\*[^*]+\*\*)/g).map((m, j) =>
          m.startsWith("**") && m.endsWith("**") ? <b key={j}>{m.slice(2, -2)}</b> : <Fragment key={j}>{m}</Fragment>,
        );
        return (
          <p key={i} className={puce ? "puce" : undefined}>
            {morceaux}
          </p>
        );
      })}
    </>
  );
}

export default function Assistant({ population }: { population: Population }) {
  const [ouvert, setOuvert] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [attente, setAttente] = useState(false);
  const fil = useRef<HTMLDivElement>(null);
  const routeur = useRouter();

  useEffect(() => {
    fil.current?.scrollTo({ top: fil.current.scrollHeight, behavior: "smooth" });
  }, [messages, attente]);

  const poser = async (texte: string) => {
    const q = texte.trim();
    if (!q || attente) return;
    setMessages((m) => [...m, { auteur: "moi", texte: q }]);
    setQuestion("");
    setAttente(true);
    try {
      const r = await envoyer<Reponse>("/api/assistant", { question: q, population });
      setMessages((m) => [...m, { auteur: "sentinelle", ...r }]);
    } catch {
      setMessages((m) => [...m, { auteur: "sentinelle", reponse: "L'API ne répond pas. Vérifiez qu'elle tourne sur le port 8000.", sources: [], liens: [], mode: "hors ligne" }]);
    } finally {
      setAttente(false);
    }
  };

  return (
    <>
      {!ouvert ? (
        <button className="bulle-assistant ne-pas-imprimer" onClick={() => setOuvert(true)}>
          <Logo taille={28} />
          Demander à Sentinelle
        </button>
      ) : null}
      {ouvert ? (
        <section className="assistant ne-pas-imprimer" aria-label="Assistant Sentinelle">
          <div className="assistant-entete">
            <Logo taille={30} />
            <div>
              <b>Assistant Sentinelle</b>
              <small>Réponses tirées des données du tableau de bord</small>
            </div>
            <button className="bouton-icone" onClick={() => setOuvert(false)} aria-label="Fermer l'assistant">
              <IconeFermer />
            </button>
          </div>

          <div className="assistant-fil" ref={fil}>
            {messages.length === 0 ? (
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => poser(s)}>
                    {s}
                  </button>
                ))}
              </div>
            ) : null}
            {messages.map((m, i) =>
              m.auteur === "moi" ? (
                <div key={i} className="message moi">
                  {m.texte}
                </div>
              ) : (
                <div key={i} className="message sentinelle">
                  <Texte texte={m.reponse} />
                  {m.liens.length ? (
                    <div className="liens-reponse">
                      {m.liens.map((l) => (
                        <button key={l.pcode} onClick={() => routeur.push(avecPopulation(`/province/${l.pcode}`, population))}>
                          {l.province} ›
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {m.sources.length ? (
                    <details className="sources-reponse">
                      <summary>Sources ({m.sources.length})</summary>
                      <ul>
                        {m.sources.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </div>
              ),
            )}
            {attente ? <div className="message sentinelle attente">Recherche dans les données…</div> : null}
          </div>

          <form
            className="assistant-saisie"
            onSubmit={(e) => {
              e.preventDefault();
              poser(question);
            }}
          >
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Posez une question sur une province, une région…" aria-label="Question" />
            <button type="submit" className="bouton" disabled={attente || !question.trim()}>
              Envoyer
            </button>
          </form>
        </section>
      ) : null}
    </>
  );
}
