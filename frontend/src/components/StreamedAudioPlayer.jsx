import { useEffect, useRef } from "react";

const StreamedAudioPlayer = ({ text, voice = "nova" }) => {
  const audioRef = useRef(null);

  useEffect(() => {
    const playAudio = async () => {
      const res = await fetch(
        `/api/speak-stream?text=${encodeURIComponent(text)}&voice=${voice}`
      );
      const reader = res.body.getReader();
      const chunks = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }

      const blob = new Blob(chunks, { type: "audio/ogg" });
      const audioUrl = URL.createObjectURL(blob);
      audioRef.current.src = audioUrl;
      audioRef.current.play();
    };

    if (text) playAudio();
  }, [text, voice]);

  return <audio ref={audioRef} controls />;
};

export default StreamedAudioPlayer;
