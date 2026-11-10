"""Spanish request words mapped to the English words memory items use, and the
filler words of dictated speech: data for `engine/recall.py`.

Why a table: the owner writes and dictates in Spanish, every memory item is
English, and recall compares words. A Spanish request used to share no word
with memory, so it returned nothing while its translation returned three
items (findings e2e-trial-09 and learning-16). A translation step would cost
a model call on every recall; a table costs a dictionary look-up.

Rules the table keeps (tests/test_r4_m.py checks them on the frozen items in
evals/recall_snapshot/):

- A target is a word the memory items contain. A translation that memory
  never uses would count against the query exactly as the Spanish word did.
- One target per word, or two alternatives joined with ``|`` when Spanish
  has one word where the items use two (``cambiar`` is change or switch).
  Recall treats the alternatives as one unit of the query.
- No key is an English word that memory uses, so an English request is never
  rewritten. False friends (``actual``, ``red``, ``sea``, ``resume``) are
  left out on purpose.
- Keys are stored without accents and lower-case, the way recall folds a
  query. Verb entries are infinitives; their common forms are generated
  (``arreglar`` covers arregla, arreglo, arreglando, arreglado, arreglalo).
  ``inf/stem2`` adds the forms of a second stem (``probar/prueb``).
"""
from __future__ import annotations

import functools

# Dictation fillers, English and Spanish: words that carry no topic. Each one
# left in a query is a term memory does not contain, which lowers every
# item's coverage of the query and turns a hit into silence.
FILLERS = frozenset(
    "ok okay uh um uhm erm hmm eh hey please pls basically actually literally really just like want "
    "wanna gonna gotta whether oops listen "
    "bueno pues vale venga oye porfa porfavor claro digamos "
    "quiero quieres quiere quieren queremos queria quisiera querria gustaria".split())
FILLER_PHRASES = tuple(tuple(p.split()) for p in (
    "you know", "i mean", "i think", "i guess", "kind of", "sort of", "o sea", "es decir", "a ver", "en plan",
    "la verdad", "por favor"))

# Spanish function words: articles, prepositions, pronouns, auxiliaries and
# question words. (The oldest twenty are also in recall.STOP.)
ES_STOP = frozenset(
    "el la los las un una unos unas y o u e ni de del al a en que por para con sin sobre entre hasta desde hacia "
    "segun durante mediante contra es son era eran fue fueron ser sido siendo soy somos esta estan estaba "
    "estoy estamos estar estes esten este esto estos estas ese esa eso esos esas aquel aquella lo le les se me te nos "
    "mi mis tu tus su sus nuestro nuestra yo ella ellos ellas usted nosotros si no ya muy mas tambien tampoco "
    "pero sino aunque porque como cuando donde cual cuales quien quienes cuanto cuanta he ha has han hemos habia "
    "hay haber hace hacer haz hazme hazlo hago hacen hacemos haga hagas hice hizo hiciera haciendo puedo puedes puede "
    "pueden podemos poder podria podrias debo debes debe deben deberia deberian debemos tener tengo tiene tienes "
    "tienen tenemos tenga voy vas va vamos van ir algo alguien alguno alguna algunos algunas todo toda todos todas "
    "cada tan tanto asi aqui ahi alli alla ahora luego entonces mientras tal quiza quizas rato dime "
    "da dan dar doy queda quedan quedar quedarse quedando quedo".split())

# Verbs by infinitive. Regular forms are generated from the infinitive, and
# from each extra stem after a slash.
_VERBS = """
arreglar=fix corregir/corrig/corrij=fix reparar=fix solucionar=fix
probar/prueb=test testear=test comprobar/comprueb=check chequear=check verificar/verifiqu=verify validar=verify
revisar=review auditar=audit
publicar/publiqu=release desplegar/desplieg/despliegu=deploy|deployment subir=push empujar=push
ejecutar=run correr=run lanzar/lanc=run
escribir=write redactar=write reescribir=rewrite
construir/construy=build compilar=build montar=build
borrar=delete eliminar=delete|remove quitar=remove
saltar=skip omitir=skip
cambiar=change|switch
mantener/mantien/manteng=keep conservar=keep guardar=save|keep almacenar=store
investigar/investigu=research delegar/delegu=delegate automatizar/automatic=automation
planificar/planifiqu=plan planear=plan
fallar=fail|failure
buscar/busqu=search encontrar/encuentr=find
mostrar/muestr=show ensenar=show
preguntar=ask|question responder=reply|answer contestar=reply|answer
detener/detien/deteng=stop
revertir/reviert/revirt=revert
registrar=record
empezar/empiez/empiec=start comenzar/comienz/comienc=start iniciar=start arrancar/arranqu=start
terminar=end acabar=end
limitar=limit necesitar=need
pegar/pegu=paste copiar=copy
medir/mid=measure limpiar=clean aprender=learn anotar=note apuntar=note afirmar=claim
cargar/cargu=load resolver/resuelv=resolve forzar/fuerz/forc=force
pulsar=click pinchar=click contar/cuent=count explicar/expliqu=explain
programar=schedule bloquear=block compartir=share enviar=send mandar=send esperar=wait
llamar=call imprimir=print mover/muev=move existir=exist
anadir=add agregar/agregu=add abrir=open cerrar/cierr=close editar=edit mirar=look
aplicar/apliqu=apply pensar/piens=think separar=separate juzgar/juzgu=judge
reanudar=resume retomar=resume continuar=continue seguir/sigu/sig=continue
comparar=compare preferir/prefier=prefer presentar=present clonar=clone
traducir/traduzc/traduj=translate reproducir/reproduzc/reproduj=reproduce
reintentar=retry repetir/repit=repeat entregar/entregu=deliver
instalar=install actualizar/actualic=update
reemplazar/reemplac=replace sustituir/sustituy=replace
disenar=design generar=generate analizar/analic=analysis
migrar=migrate
pagar/pagu=paid gastar=cost citar=cite pedir/pid=ask|request decidir=decide
durar=last llenar=fill trabajar=work formatear=format
"""

# Words that do not conjugate here: nouns, adjectives, adverbs, numbers, and
# the forms of short or irregular verbs written out. A plural is generated.
_WORDS = """
regla=rule norma=rule coste=cost costo=cost gasto=cost dueno=owner propietario=owner
comprobacion=check chequeo=check verificacion=verify validacion=verify
sesion=session trabajo=work|job proyecto=project nunca=never jamas=never
ejecucion=run primero=first primera=first primer=first antes=before
archivo=file fichero=file estado=state|status datos=data dato=data lectura=read
modelo=model exactitud=accuracy investigacion=research codigo=code fuente=source nombre=name
esfuerzo=effort hecho=done terminado=done listo=done acabado=done nuevo=new nueva=new guion=script
publicacion=release lanzamiento=release despliegue=deployment|deploy
traduccion=translation grande=large enorme=large tamano=size pequeno=small pequena=small
delegacion=delegation revisor=reviewer revisora=reviewer salida=output
informe=report reporte=report plataforma=platform otro=other otra=other
prueba=test|evidence paso=step memoria=memory nada=nothing palabra=word agente=agent subagente=subagent
automatizacion=automation cambio=change entero=whole entera=whole completo=full|whole completa=full|whole
pago=paid entrada=input alto=high alta=high atras=back vuelta=back
ayudante=helper bajo=low baja=low mayoria=most evidencia=evidence
falta=missing faltante=missing mismo=same misma=same repositorio=repo|repository
segundo=second segunda=second vez=time veces=time largo=long larga=long
movil=phone telefono=phone celular=phone conversacion=conversation linea=line
peticion=request solicitud=request encargo=brief|request despues=after tras=after contexto=context
resultado=result fallo=failure|fail fallido=fail|failure fallida=fail|failure busqueda=search
calidad=quality defecto=defect pregunta=question|ask limite=limit cuota=quota
externo=outside externa=outside fuera=outside dos=two tres=three ambos=both
principal=main lista=list registro=record|log muestra=sample|show
idioma=language lengua=language lenguaje=language
numero=number cifra=number incorrecto=wrong erroneo=wrong equivocado=wrong tiempo=time fecha=date
inicio=start tarea=task|job frase=sentence exacto=exact exacta=exact texto=text respuesta=reply|answer
respaldo=fallback alternativa=fallback modo=mode verde=green rojo=red
maquina=machine ordenador=computer computadora=computer
limpio=clean limpia=clean limpieza=clean integracion=integration clave=key llave=key
precio=price siempre=always muchos=many muchas=many demasiados=many demasiadas=many cuantos=many cuantas=many
captura=screenshot pantallazo=screenshot pantalla=screen mitad=mid|half relevo=handover traspaso=handover
fiabilidad=reliability ruta=path|route seguridad=safety|security solo=only|alone sola=only|alone solamente=only
auditoria=audit aprendizaje=learning nota=note apunte=note afirmacion=claim progreso=progress avance=progress
razon=reason motivo=reason instruccion=instruction creativo=creative creativa=creative leccion=lesson
carga=load ajustes=settings configuracion=settings rapido=fast rapida=fast
ultimo=latest|last ultima=latest|last clic=click comando=command orden=order|command pagina=page
entregable=deliverable entrega=delivery|deliver conteo=count recuento=count vigente=current
corto=short corta=short breve=short explicacion=explain edicion=edition identico=identical identica=identical
servicio=service lector=reader tabla=table interfaz=interface programado=scheduled programada=scheduled
bloqueado=blocked bloqueo=blocked profundidad=depth pocos=few pocas=few compartido=shared
barato=cheap|cheaper barata=cheap|cheaper economico=cheap|cheaper paralelo=parallel independiente=independent
envio=send espera=wait turno=turn llamada=call menos=less frio=cold seguro=safe segura=safe
nivel=level mensaje=message lugar=place sitio=place metodo=method ronda=round documento=document
abierto=open escrito=written requisito=requirement historial=history historia=history binario=binary
varios=several varias=several vacio=empty vacia=empty rama=branch sencillo=plain tercero=third tercer=third
herramienta=tool resumen=summary resumenes=summary
ejemplo=example generico=generic sistema=system minuto=minute credito=credit
suscripcion=subscription interno=internal separado=separate aparte=separate direccion=address caja=box
copia=copy navegador=browser numerado=numbered gusto=taste voz=voice audiencia=audience aplicacion=app
nativo=native espanol=spanish castellano=spanish ingles=english significado=meaning sentido=meaning disco=disk
forma=way manera=way analisis=analysis fila=row proceso=process detras=behind credencial=credential
objetivo=target articulo=article etiqueta=tag enlace=link vinculo=link
documentacion=documentation presente=present longitud=length glosario=glossary paridad=parity
ancho=width anchura=width malo=bad mala=bad dia=day proposito=purpose mapa=map clon=clone
produccion=production cita=citation ruidoso=noisy ruidosa=noisy
duplicado=duplicate duplicada=duplicate valor=value opcion=option millon=million formato=format duracion=last
paralela=parallel libreria=library biblioteca=library
capitulo=chapter libro=book cronograma=schedule rutina=routine
boton=button icono=icon imagen=image parrafo=paragraph
ley=law presentacion=presentation
"""

# Forms of short or irregular verbs, written out; no plural is generated.
_FORMS = """
lee=read leo=read leer=read leyendo=read leido=read
volver=back vuelve=back vuelvo=back vuelven=back volviendo=back vuelto=back
uso=usage|use usar=use|usage usan=use|usage usando=use|usage usado=use|usage usamos=use|usage
parar=stop paro=stop paran=stop paren=stop parando=stop parado=stop parada=stop
deshacer=revert|undo deshaz=revert|undo deshago=revert|undo deshecho=revert|undo
pon=put pone=put poner=put pongo=put ponle=put
ver=see|look veo=see|look vemos=see|look viendo=see|look visto=see|look
sabe=know sabes=know saben=know sabemos=know saber=know
faltan=missing faltar=missing resumir=summary resumido=summary resumeme=summary mal=bad|wrong
pasa=pass pasan=pass pasar=pass pasando=pass pasado=pass pase=pass pasen=pass
"""

# English words a generated or listed Spanish form would otherwise hit
# ("quite" from quitar, "page" from pagar, "media" from medir): never keys.
_ENGLISH = frozenset(
    "cargo compile compiles fallen fines gusto lance lances llama llamas males media median medias mire page pages "
    "pagan pare pares probe probes pulse pulses quite revise revises segue usa valor".split())

# Phrases whose words mean something else one at a time.
_PHRASES = """
captura de pantalla=screenshot capturas de pantalla=screenshot segundo plano=background
por defecto=default dos veces=twice una vez=once mayor parte=most en vez de=instead en lugar de=instead
copia de seguridad=backup punto de control=checkpoint otra vez=again de nuevo=again hoja de ruta=roadmap
base de datos=database a fondo=deep linea de comandos=command se ve=look se ven=look como es debido=right|way
sin peligro=safe a la vez=parallel al mismo tiempo=parallel
"""

_AR = ("a o as an amos e es en emos ar ando ado ada ados adas aba aban aste aron "
       "alo ala alos alas ame ale elo ela eme").split()
_ER = ("e o es en emos imos a as an amos er ir iendo ido ida idos idas ia ian io ieron iera "
       "elo ela eme alo ala ame").split()
_CLITICS = ("se", "lo", "la", "los", "las", "le", "me", "te", "nos")


def _alts(target: str) -> tuple[str, ...]:
    return tuple(target.split("|"))


def _pairs(block: str):
    for entry in block.split():
        key, target = entry.split("=")
        yield key, _alts(target)


def _verb_forms(entry: str) -> list[str]:
    inf, *extra = entry.split("/")
    forms = [inf] + [inf + cl for cl in _CLITICS]
    endings = _AR if inf.endswith("ar") else _ER
    for stem in [inf[:-2], *extra]:
        forms += [stem + e for e in endings]
    gerund = inf[:-2] + ("ando" if inf.endswith("ar") else "iendo")
    return forms + [gerund + cl for cl in _CLITICS]


def _plural(word: str) -> str:
    if word.endswith("z"):
        return word[:-1] + "ces"
    return word + ("s" if word[-1] in "aeiou" else "" if word.endswith("s") else "es")


@functools.lru_cache(maxsize=1)
def table() -> dict[str, tuple[str, ...]]:
    """Every Spanish word form the glossary knows -> its English alternatives.
    Built once per process, on the first look-up."""
    out: dict[str, tuple[str, ...]] = {}
    for entry, target in _pairs(_VERBS):
        for form in _verb_forms(entry):
            out.setdefault(form, target)
    for word, target in _pairs(_WORDS):  # a written-out word wins over a generated verb form
        out[word] = out[_plural(word)] = target
    out.update(_pairs(_FORMS))
    for word in _ENGLISH:
        out.pop(word, None)
    return out


@functools.lru_cache(maxsize=1)
def phrases() -> dict[tuple[str, ...], tuple[str, ...]]:
    """Spanish phrases of two or three words -> their English alternatives."""
    out: dict[tuple[str, ...], tuple[str, ...]] = {}
    words: list[str] = []
    for tok in _PHRASES.split():  # "captura de pantalla=screenshot": the target ends each phrase
        if "=" in tok:
            last, target = tok.split("=")
            out[tuple(words + [last])] = _alts(target)
            words = []
        else:
            words.append(tok)
    return out


def base_terms() -> int:
    """How many Spanish terms were written by hand (verbs, words, forms, phrases)."""
    return len(_VERBS.split()) + len(_WORDS.split()) + len(_FORMS.split()) + len(phrases())


def _drop_phrases(tokens: list[str], table_: tuple[tuple[str, ...], ...]) -> list[str]:
    out, i = [], 0
    while i < len(tokens):
        hit = next((p for p in table_ if tuple(tokens[i:i + len(p)]) == p), None)
        if hit:
            i += len(hit)
        else:
            out.append(tokens[i])
            i += 1
    return out


def units(tokens: list[str], stop: frozenset = frozenset()) -> list[tuple[str, ...]]:
    """The topic of a request as units of meaning, in order: one tuple of
    English alternatives per word that is kept. ``tokens`` are folded
    (lower-case, no accents). Fillers, the caller's stop-words and Spanish
    function words are dropped; a Spanish term becomes the English word memory
    uses; any other word stands for itself."""
    tokens = _drop_phrases(tokens, FILLER_PHRASES)
    ph, tb = phrases(), table()
    out: list[tuple[str, ...]] = []
    i = 0
    while i < len(tokens):
        hit = next((tuple(tokens[i:i + n]) for n in (3, 2) if tuple(tokens[i:i + n]) in ph), None)
        if hit:
            out.append(ph[hit])
            i += len(hit)
            continue
        w = tokens[i]
        i += 1
        if w in stop or w in FILLERS or w in ES_STOP:
            continue
        out.append(tb.get(w, (w,)))
    return list(dict.fromkeys(out))
