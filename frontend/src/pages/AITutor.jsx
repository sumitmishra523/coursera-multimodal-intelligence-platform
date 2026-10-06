import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import OndemandVideoIcon from "@mui/icons-material/OndemandVideo";
import PlayCircleFilledIcon from "@mui/icons-material/PlayCircleFilled";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Avatar,
  Stack,
  CircularProgress,
  IconButton,
  MenuItem,
  Alert,
  Divider,
  Chip,
} from "@mui/material";

import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";
import SendIcon from "@mui/icons-material/Send";
import DeleteIcon from "@mui/icons-material/Delete";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import MenuBookIcon from "@mui/icons-material/MenuBook";


import Layout from "../components/Layout";
import api from "../api/api";

function AITutor() {
  const navigate = useNavigate();

  // ---------------------------------
  // Courses
  // ---------------------------------

  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [coursesLoading, setCoursesLoading] = useState(true);

  // ---------------------------------
  // Chat
  // ---------------------------------

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  // ---------------------------------
  // Error
  // ---------------------------------

  const [error, setError] = useState("");

  // ---------------------------------
  // Auto Scroll
  // ---------------------------------

  const chatEndRef = useRef(null);

  // ---------------------------------
  // Load Courses
  // ---------------------------------

  useEffect(() => {
    fetchCourses();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loading]);

  async function fetchCourses() {
    try {
      setCoursesLoading(true);
      setError("");

      const response = await api.get("/courses");

      console.log(
        "COURSES API RESPONSE:",
        response.data
      );

      setCourses(response.data);

      // Automatically select first course
      if (
        response.data.length > 0 &&
        !courseId
      ) {
        setCourseId(
          String(response.data[0].course_id)
        );
      }
    } catch (err) {
      console.error(
        "Unable to load courses:",
        err
      );

      setError(
        err.response?.data?.detail ||
          "Unable to load courses."
      );
    } finally {
      setCoursesLoading(false);
    }
  }

  // ---------------------------------
  // Quick Question
  // ---------------------------------

  function askQuickQuestion(text) {
    if (loading || !courseId) {
      return;
    }

    setQuestion(text);
  }

  // ---------------------------------
  // Ask AI
  // ---------------------------------

  async function askAI() {
    if (!question.trim()) {
      return;
    }

    if (!courseId) {
      setError(
        "Please select a course first."
      );
      return;
    }

    const userQuestion = question.trim();

    // Add user message immediately
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: userQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await api.post(
        "/course-rag-chat",
        {
          course_id: Number(courseId),
          question: userQuestion,
        }
      );

      console.log(
        "AI RESPONSE:",
        response.data
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.data.answer,
          evidence:
            response.data.evidence || [],
          chunksUsed:
            response.data.chunks_used || 0,
        },
      ]);
    } catch (err) {
      console.error(
        "AI Tutor error:",
        err
      );

      console.error(
        "STATUS:",
        err.response?.status
      );

      console.error(
        "DATA:",
        err.response?.data
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text:
            err.response?.data?.detail ||
            "Failed to get AI response.",
          evidence: [],
          chunksUsed: 0,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------
  // Enter Key
  // ---------------------------------

  function handleKeyDown(e) {
    if (
      e.key === "Enter" &&
      !e.shiftKey
    ) {
      e.preventDefault();
      askAI();
    }
  }

  // ---------------------------------
  // Clear Chat
  // ---------------------------------

  function clearChat() {
    setMessages([]);
    setError("");
  }

  // ---------------------------------
  // Course Change
  // ---------------------------------

  function handleCourseChange(e) {
    setCourseId(e.target.value);

    // Clear old conversation because
    // conversation belongs to previous course
    setMessages([]);
    setError("");
  }

  // ---------------------------------
  // Copy Answer
  // ---------------------------------

  async function copyMessage(text) {
    try {
      await navigator.clipboard.writeText(
        text
      );
    } catch (err) {
      console.error(
        "Copy failed:",
        err
      );
    }
  }
  function formatTime(seconds) {
  if (seconds == null) {
    return "00:00";
  }

  const totalSeconds = Math.floor(
    Number(seconds)
  );

  const minutes = Math.floor(
    totalSeconds / 60
  );

  const remainingSeconds =
    totalSeconds % 60;

  return `${String(minutes).padStart(
    2,
    "0"
  )}:${String(
    remainingSeconds
  ).padStart(2, "0")}`;
}

  // ---------------------------------
  // Selected Course
  // ---------------------------------

  const selectedCourse = courses.find(
    (course) =>
      String(course.course_id) ===
      String(courseId)
  );

  return (
    <Layout>
      <Box
        sx={{
          maxWidth: 1100,
          mx: "auto",
          py: 4,
          px: 2,
        }}
      >

        {/* -------------------------------- */}
        {/* Header */}
        {/* -------------------------------- */}

        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          mb={3}
        >
          <Button
            startIcon={<ArrowBackIcon />}
            variant="outlined"
            onClick={() =>
              navigate(-1)
            }
          >
            Back
          </Button>

          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
          >
            <SmartToyIcon
              sx={{
                color: "#7C3AED",
                fontSize: 32,
              }}
            />

            <Typography
              variant="h4"
              fontWeight="bold"
            >
              AI Tutor
            </Typography>
          </Stack>

          <IconButton
            color="error"
            onClick={clearChat}
            disabled={
              messages.length === 0
            }
          >
            <DeleteIcon />
          </IconButton>
        </Stack>

        {/* -------------------------------- */}
        {/* Error */}
        {/* -------------------------------- */}

        {error && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            onClose={() =>
              setError("")
            }
          >
            {error}
          </Alert>
        )}

        {/* -------------------------------- */}
        {/* Course Selection */}
        {/* -------------------------------- */}

        <Paper
          elevation={2}
          sx={{
            p: 3,
            mb: 3,
            borderRadius: 3,
          }}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            mb={2}
          >
            <MenuBookIcon color="primary" />

            <Typography
              variant="h6"
              fontWeight="bold"
            >
              Select Course
            </Typography>
          </Stack>

          <TextField
            select
            fullWidth
            label="Course"
            value={courseId}
            onChange={handleCourseChange}
            disabled={coursesLoading}
            helperText={
              coursesLoading
                ? "Loading courses..."
                : "AI will answer using the selected course material."
            }
          >
            <MenuItem value="">
              Select a course
            </MenuItem>

            {courses.map((course) => (
              <MenuItem
                key={course.course_id}
                value={course.course_id}
              >
                {course.title}
              </MenuItem>
            ))}
          </TextField>

          {selectedCourse && (
            <Chip
              label={`Using: ${selectedCourse.title}`}
              color="primary"
              variant="outlined"
              sx={{ mt: 2 }}
            />
          )}
        </Paper>

        {/* -------------------------------- */}
        {/* Chat Window */}
        {/* -------------------------------- */}

        <Paper
          elevation={3}
          sx={{
            height: "60vh",
            overflowY: "auto",
            p: 3,
            borderRadius: 4,
            mb: 3,
            bgcolor: "#F8FAFC",
          }}
        >

          {/* Empty State */}

          {messages.length === 0 && (
            <Box
              sx={{
                mt: 10,
                textAlign: "center",
              }}
            >
              <Avatar
                sx={{
                  width: 70,
                  height: 70,
                  mx: "auto",
                  mb: 2,
                  bgcolor: "#7C3AED",
                }}
              >
                <SmartToyIcon
                  fontSize="large"
                />
              </Avatar>

              <Typography
                variant="h5"
                fontWeight="bold"
                gutterBottom
              >
                Welcome to AI Tutor
              </Typography>

              <Typography
                color="text.secondary"
                sx={{
                  maxWidth: 600,
                  mx: "auto",
                  mb: 3,
                }}
              >
                Ask questions from your
                uploaded course material.
                The AI Tutor uses RAG to
                retrieve relevant course
                content before answering.
              </Typography>

              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 1 }}
              >
                Try asking:
              </Typography>

              <Stack
                direction="row"
                spacing={1}
                justifyContent="center"
                flexWrap="wrap"
                useFlexGap
              >
                {[
                  "Explain the Central Limit Theorem",
                  "What is this topic about?",
                  "Explain this concept with an example",
                ].map((prompt) => (
                  <Button
                    key={prompt}
                    size="small"
                    variant="outlined"
                    onClick={() =>
                      askQuickQuestion(prompt)
                    }
                    disabled={!courseId || loading}
                    sx={{
                      borderRadius: 3,
                      textTransform: "none",
                      mb: 1,
                    }}
                  >
                    {prompt}
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          {/* Messages */}

          {messages.map(
            (msg, index) => (
              <Box key={index} mb={4}>

                <Stack
                  direction="row"
                  spacing={2}
                  justifyContent={
                    msg.role === "user"
                      ? "flex-end"
                      : "flex-start"
                  }
                  alignItems="flex-start"
                >

                  {/* AI Avatar */}

                  {msg.role ===
                    "assistant" && (
                    <Avatar
                      sx={{
                        bgcolor:
                          "#7C3AED",
                      }}
                    >
                      <SmartToyIcon />
                    </Avatar>
                  )}

                  {/* Message */}

                  <Paper
                    elevation={1}
                    sx={{
                      p: 2,
                      maxWidth:
                        msg.role ===
                        "user"
                          ? "75%"
                          : "85%",
                      bgcolor:
                        msg.role ===
                        "user"
                          ? "#6366F1"
                          : "#EEF2FF",
                      color:
                        msg.role ===
                        "user"
                          ? "#fff"
                          : "#000",
                      borderRadius: 3,
                    }}
                  >
                    <ReactMarkdown>
                      {msg.text}
                    </ReactMarkdown>

                    {/* Copy Button */}

                    {msg.role ===
                      "assistant" && (
                      <Button
                        size="small"
                        startIcon={
                          <ContentCopyIcon />
                        }
                        sx={{
                          mt: 1,
                        }}
                        onClick={() =>
                          copyMessage(
                            msg.text
                          )
                        }
                      >
                        Copy
                      </Button>
                    )}
                  </Paper>

                  {/* User Avatar */}

                  {msg.role === "user" && (
                    <Avatar
                      sx={{
                        bgcolor:
                          "#4F46E5",
                      }}
                    >
                      <PersonIcon />
                    </Avatar>
                  )}

                </Stack>

                {/* -------------------------------- */}
                {/* Retrieved Evidence */}
                {/* -------------------------------- */}

                {msg.role ===
                  "assistant" &&
                  msg.evidence &&
                  msg.evidence.length >
                    0 && (
                    <Paper
                      variant="outlined"
                      sx={{
                        mt: 2,
                        ml: 7,
                        p: 2,
                        borderRadius: 3,
                        bgcolor: "#FFFFFF",
                      }}
                    >

                      <Stack
                        direction="row"
                        spacing={1}
                        alignItems="center"
                        mb={1}
                      >
                        <PictureAsPdfIcon
                          color="primary"
                        />

                        <Typography
                          variant="h6"
                          fontWeight="bold"
                        >
                          Retrieved Evidence
                        </Typography>

                        <Chip
                          size="small"
                          label={`${msg.chunksUsed} chunks`}
                          color="primary"
                          variant="outlined"
                        />

                        <Chip
                          size="small"
                          label={`${msg.evidence.length} sources`}
                          variant="outlined"
                        />
                      </Stack>

                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mb: 2 }}
                      >
                        These course-material
                        chunks were retrieved
                        by the RAG system to
                        generate this answer.
                      </Typography>

                      <Divider
                        sx={{ mb: 2 }}
                      />

                      <Stack spacing={2}>

                        {msg.evidence.map(
                          (evidence) => (
                            <Paper
                              key={
                                evidence.id
                              }
                              variant="outlined"
                              sx={{
                                p: 2,
                                borderRadius: 2,
                              }}
                            >

                              {/* Evidence Header */}

                          

                                <Stack
  direction="row"
  spacing={1}
  flexWrap="wrap"
>
  {evidence.source === "video" ? (
  <>
    <Chip
      size="small"
      icon={<OndemandVideoIcon />}
      label="Video"
      color="primary"
      variant="outlined"
    />

    <Chip
      size="small"
      label={
        evidence.video_title ||
        "Course Video"
      }
      variant="outlined"
    />

    {evidence.start_time != null &&
      evidence.end_time != null && (
        <>
          <Chip
            size="small"
            label={`⏱ ${formatTime(
              evidence.start_time
            )} – ${formatTime(
              evidence.end_time
            )}`}
            variant="outlined"
          />

          <Button
            size="small"
            variant="contained"
            startIcon={
              <PlayCircleFilledIcon />
            }
            onClick={() =>
              navigate(`/course/${courseId}`, {
                state: {
                  targetVideoId:
                    evidence.video_id,
                  seekTime:
                    evidence.start_time,
                },
              })
            }
          >
            Watch Evidence
          </Button>
        </>
      )}
  </>
) : (
  <>
    <Chip
      size="small"
      icon={<PictureAsPdfIcon />}
      label={
        evidence.source ||
        "Unknown source"
      }
      variant="outlined"
    />

      <Chip
        size="small"
        label={`Page: ${
          evidence.page ??
          "Unknown"
        }`}
        variant="outlined"
      />

      <Chip
        size="small"
        label={`Chunk: ${
          evidence.chunk ??
          "Unknown"
        }`}
        variant="outlined"
      />
    </>
  )}
</Stack>

                              {/* Evidence Text */}

                              <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{
                                  
                                  lineHeight: 1.7,
                                }}
                              >
                                
                                {evidence.text?.replace(/\s+/g, " ").trim()}
                                
                              </Typography>

                            </Paper>
                          )
                        )}

                      </Stack>

                    </Paper>
                  )}

              </Box>
            )
          )}

          {/* -------------------------------- */}
          {/* AI Loading */}
          {/* -------------------------------- */}

          {loading && (
            <Stack
              direction="row"
              spacing={2}
              alignItems="center"
            >
              <Avatar
                sx={{
                  bgcolor:
                    "#7C3AED",
                }}
              >
                <SmartToyIcon />
              </Avatar>

              <CircularProgress
                size={22}
              />

              <Typography
                fontWeight="bold"
              >
                AI is thinking...
              </Typography>
            </Stack>
          )}

          <div ref={chatEndRef} />

        </Paper>

        {/* -------------------------------- */}
        {/* Question Input */}
        {/* -------------------------------- */}

        <Stack
          direction={{
            xs: "column",
            sm: "row",
          }}
          spacing={2}
        >

          <TextField
            fullWidth
            multiline
            minRows={2}
            maxRows={5}
            variant="outlined"
            placeholder={
              courseId
                ? "Ask something from the course material..."
                : "Select a course first..."
            }
            value={question}
            onChange={(e) =>
              setQuestion(
                e.target.value
              )
            }
            onKeyDown={
              handleKeyDown
            }
            disabled={
              !courseId || loading
            }
          />

          <Button
            variant="contained"
            size="large"
            endIcon={<SendIcon />}
            disabled={
              !courseId ||
              !question.trim() ||
              loading
            }
            onClick={askAI}
            sx={{
              minWidth: 160,
              borderRadius: 3,
            }}
          >
            {loading
              ? "Thinking..."
              : "Ask AI"}
          </Button>

        </Stack>

      </Box>
    </Layout>
  );
}

export default AITutor;