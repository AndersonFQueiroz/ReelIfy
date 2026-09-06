"""
Serviço de Inteligência Artificial via Google Gemini API (100% Gratuito).
Usa o SDK novo `google.genai` (google-genai) com o modelo gemini-flash-latest.
Gera roteiros de alta conversão de exatamente 20 segundos para vídeos curtos para afiliados.
"""
import json
import logging
from typing import Optional

from config.settings import settings
from bot.services.queue_service import ScriptData

logger = logging.getLogger(__name__)

GEMINI_SYSTEM_INSTRUCTION = """
Você é um copywriter de elite especializado em roteiros de alta conversão para vídeos curtos de 20 segundos (YouTube Shorts, Reels, TikTok) promovendo produtos afiliados.
Sua missão é criar um roteiro magnético, persuasivo e natural para ser narrado ou legendado no vídeo.

REGRAS RÍGIDAS:
1. DURAÇÃO EXATA DE 20 SEGUNDOS: O texto completo deve conter entre 45 e 55 palavras faladas no total (ritmo perfeito de fala).
2. PORTUGUÊS DO BRASIL: Tom dinâmico, natural e envolvente. Evite termos genéricos ou robóticos.
3. ESTRUTURA EM 5 PARTES:
   - Gancho (0-3s): Pergunta provocativa ou fato curioso para prender a atenção.
   - Problema (3-8s): A dor cotidiana que o produto resolve.
   - Solução (8-14s): O produto em ação e seu benefício principal.
   - Prova Social / Diferencial (14-17s): Por que confiar (avaliações, economia, praticidade).
   - CTA (17-20s): Chamada direta para o link da bio/descrição.
4. USE O PÚBLICO-ALVO COM GRAMÁTICA NATURAL: o público informado não deve ser encaixado literalmente depois de "você faz parte de". Para "pais", use "pais sabem...", "para pais..." ou "se você é pai ou mãe...".
5. Em regenerações, mude de verdade o gancho, a dor e a construção do texto. Não repita o roteiro anterior.

RETORNE EXCLUSIVAMENTE UM OBJETO JSON VÁLIDO com as seguintes chaves:
{
  "hook": "texto do gancho",
  "problem": "texto do problema",
  "solution": "texto da solução",
  "proof": "texto da prova social",
  "cta": "texto da chamada para ação",
  "full_text": "texto corrido unificado para ser narrado em 20 segundos"
}
"""


class GeminiService:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa a conexão com o Google Gemini usando o SDK novo (google.genai)."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY não informada. O GeminiService funcionará em modo fallback/mock.")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Cliente Google Gemini ({self.model_name}) inicializado com sucesso via google.genai.")
        except Exception as e:
            logger.error(f"Erro ao inicializar Google Gemini SDK: {e}")
            self._client = None

    async def generate_script(
        self,
        product_name: str,
        description: str,
        target_audience: str,
        affiliate_link: str,
        photos_count: int = 1,
        variation_index: int = 0,
    ) -> ScriptData:
        """
        Gera um roteiro estruturado de 20s a partir dos dados do produto.
        Caso a API não esteja configurada ou ocorra falha, gera um roteiro fallback.
        """
        affiliate_info = affiliate_link.strip() if affiliate_link else "Link na bio ou primeiro comentário fixado"
        angles_note = f"- Mídia Visual: O vídeo contará com {photos_count} fotos alternando ângulos e detalhes na linha do tempo.\n" if photos_count > 1 else ""
        angles = ("praticidade no dia a dia", "tempo de qualidade com a família", "conforto e facilidade de uso", "economia e custo-benefício", "um problema cotidiano inesperado")
        angle = angles[variation_index % len(angles)]

        user_prompt = (
            f"Crie um roteiro persuasivo de 20 segundos para o produto abaixo:\n"
            f"- Nome do Produto: {product_name}\n"
            f"- Principais Benefícios / Descrição: {description}\n"
            f"- Público-Alvo: {target_audience}\n"
            f"- Ângulo obrigatório desta versão: {angle}\n"
            f"- Número da versão: {variation_index + 1}. Esta versão precisa ser diferente das anteriores, se houver.\n"
            f"{angles_note}"
            f"- Link de Afiliado (para o CTA): {affiliate_info}\n"
        )

        if self._client:
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=GEMINI_SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )

                raw_text = response.text.strip()
                # Limpar possíveis marcadores markdown
                if raw_text.startswith("```json"):
                    raw_text = raw_text.removeprefix("```json").removesuffix("```").strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text.removeprefix("```").removesuffix("```").strip()

                data = json.loads(raw_text)
                script = ScriptData(
                    hook=data.get("hook", ""),
                    problem=data.get("problem", ""),
                    solution=data.get("solution", ""),
                    proof=data.get("proof", ""),
                    cta=data.get("cta", ""),
                    full_text=data.get("full_text", ""),
                )
                logger.info(f"Roteiro gerado com sucesso pelo Gemini ({self.model_name}).")
                return script

            except Exception as e:
                logger.error(f"Falha na requisição ao Gemini: {e}. Usando fallback local.")

        # Fallback local seguro para desenvolvimento offline ou falta de chave
        return self._generate_fallback_script(product_name, description, target_audience, variation_index)

    def _generate_fallback_script(
        self, product_name: str, description: str, target_audience: str, variation_index: int = 0
    ) -> ScriptData:
        audience = target_audience.strip().rstrip(".!?") or "pessoas práticas"
        audience_lower = audience.lower()
        parent_audience = any(term in audience_lower for term in ("pai", "mãe", "mae", "pais", "mães", "maes"))
        if parent_audience:
            hooks = (
                "Quem tem filhos sabe: cada minuto livre faz diferença na rotina.",
                "Pais e mães, querem mais tempo para aproveitar com a família?",
                "A rotina com filhos pode ser corrida, mas algumas tarefas podem ficar mais simples.",
                "Já pensou em ganhar praticidade sem abrir mão dos momentos em família?",
                "Quando o dia é corrido, uma solução prática muda tudo.",
            )
            problem = "Na rotina de pais e mães, encontrar praticidade ajuda a sobrar tempo para o que realmente importa."
        else:
            hooks = (
                "Já imaginou resolver isso de um jeito muito mais simples?",
                "Você ainda perde tempo com uma tarefa que poderia ser muito mais fácil?",
                "Quer mais praticidade sem complicação no dia a dia?",
                "Uma pequena mudança pode deixar sua rotina muito mais leve.",
                "Existe um jeito mais simples de resolver isso.",
            )
            problem = f"Para {audience_lower}, encontrar algo prático e de qualidade pode fazer toda a diferença."
        hook = hooks[variation_index % len(hooks)]
        solution = f"Com {product_name}, você tem {description} em poucos minutos e sem complicações."
        proof = f"Uma escolha prática para quem busca mais facilidade no dia a dia com {product_name}."
        cta = "Aproveite a promoção exclusiva no link da bio antes que o estoque acabe!"
        full_text = f"{hook} {problem} {solution} {proof} {cta}"

        return ScriptData(
            hook=hook,
            problem=problem,
            solution=solution,
            proof=proof,
            cta=cta,
            full_text=full_text,
        )


# Instância singleton global do serviço Gemini
gemini_service = GeminiService()
